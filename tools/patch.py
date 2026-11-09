"""Build/apply/restore a patch using the user's own, supported Steam game files."""
import argparse
import copy
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys

from formats import Archive, list_files, parse_text, serialize

ROOT = Path(__file__).resolve().parents[1]
SUPPORTED = json.loads((ROOT / 'tools/supported-build.json').read_text(encoding='utf-8'))
TRANSLATIONS = ROOT / 'translations/ja.json'
STATE_NAME = '.myst4-ja-patch'
PATCH_REVISION = 1


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.writing')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def detect_game():
    roots = [Path(os.environ.get('ProgramFiles(x86)', 'C:/Program Files (x86)')) / 'Steam']
    if os.name == 'nt':
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam') as key:
                roots.insert(0, Path(winreg.QueryValueEx(key, 'SteamPath')[0]))
        except OSError:
            pass
    libraries = list(roots)
    for root in roots:
        vdf = root / 'steamapps/libraryfolders.vdf'
        if vdf.is_file():
            for match in re.finditer(r'"path"\s+"([^"]+)"', vdf.read_text(encoding='utf-8', errors='replace')):
                libraries.append(Path(match[1].replace('\\\\', '\\')))
    candidates = list(dict.fromkeys(p / 'steamapps/common/Myst IV Revelation' for p in libraries))
    found = [p for p in candidates if all((p / name).is_file() for name in SUPPORTED)]
    if len(found) != 1:
        raise ValueError('ゲームフォルダーを一意に検出できません。--game-dir または -GameDir で指定してください。')
    return found[0]


def require_stopped():
    if os.name != 'nt':
        return
    result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq Myst4.exe', '/FO', 'CSV', '/NH'],
                            capture_output=True, check=True)
    for row in csv.reader(result.stdout.decode(errors='replace').splitlines()):
        if row and row[0].casefold() == 'myst4.exe':
            raise ValueError('Myst IV を終了してから実行してください。')


def validate_originals(source):
    for name, expected in SUPPORTED.items():
        path = source / name
        if not path.is_file() or digest(path) != expected:
            raise ValueError(f'未対応または変更済みのゲームデータです: {path}\n'
                             'Steamの英語版原本が必要です。ゲームデータの再取得・上書きは自動では行いません。')


def read_texts(source):
    base = Archive(source / 'data/english/data.m4b')
    patch = Archive(source / 'data/patch.m4b')
    english = Archive(patch.get('english.m4b'))
    texts = {}
    overrides = []
    for archive, is_patch in [(base, False), (english, True)]:
        for name in list_files(archive):
            if not name.endswith('.bin') or not ('/text/' in '/' + name or '/subtitle/' in '/' + name):
                continue
            texts[name] = parse_text(archive.get(name), '/subtitle/' in '/' + name)
            if is_patch:
                overrides.append(name)
    base.f.close()
    patch.f.close()
    return texts, overrides


def translate(original, payload):
    if payload.get('format_version') != 1:
        raise ValueError('翻訳データの形式に対応していません。')
    translated = copy.deepcopy(original)
    applied = 0
    for name, replacements in payload['subtitles'].items():
        obj = translated[name]
        expected = {str(i) for i, line in enumerate(obj['lines']) if line['text'].strip()}
        if expected != replacements.keys():
            raise ValueError(f'字幕区間が一致しません: {name}')
        for key, text in replacements.items():
            if not text.strip():
                raise ValueError(f'空の訳文です: {name}:{key}')
            obj['lines'][int(key)]['text'] = text
    if set(payload['subtitles']) != {name for name, obj in original.items() if 'lines' in obj}:
        raise ValueError('翻訳対象の字幕ファイルに過不足があります。')
    placeholder = re.compile(r'%(?:\d+\$)?[-+#0 ]*(?:\d+|\*)?(?:\.(?:\d+|\*))?[hlL]?[diuoxXfFeEgGaAcspn%]')
    for name, replacements in payload['menus'].items():
        for key, text in replacements.items():
            parts = key.split('/')
            node = translated[name]['strings']
            for part in parts[:-1]:
                node = node[part]
            before = node[parts[-1]]
            if not text.strip() or placeholder.findall(before) != placeholder.findall(text):
                raise ValueError(f'メニューの書式指定子または訳文が不正です: {name}:{key}')
            node[parts[-1]] = text
            applied += 1
    return translated, applied


def all_strings(objects):
    def leaves(node):
        for value in node.values():
            if isinstance(value, dict):
                yield from leaves(value)
            else:
                yield value
    for obj in objects.values():
        if 'lines' in obj:
            yield from (line['text'] for line in obj['lines'])
        else:
            yield from leaves(obj['strings'])


def build(source, output, font_path):
    from fonts import NO_END, NO_START, build_fonts, wrap
    validate_originals(source)
    original, overrides = read_texts(source)
    translated, menu_count = translate(original, load_json(TRANSLATIONS))
    data = Archive(source / 'data/data.m4b')
    glyphs, advances, font_stats = build_fonts(set(''.join(all_strings(translated))), data, font_path)
    data.f.close()
    line_count = 0
    for name, obj in translated.items():
        if 'lines' in obj:
            for line in obj['lines']:
                if not line['text'].strip():
                    continue
                line['text'] = wrap(line['text'], 600, advances)
                if len(line['text'].split('\n')) > 2:
                    raise ValueError(f'字幕が2行に収まりません: {name}')
                line_count += 1
        else:
            width = 460 if 'helpmap' in name else 400 if 'credits' in name else 430
            def reflow(node, group=None):
                for key, value in node.items():
                    if isinstance(value, dict):
                        reflow(value, key)
                    elif value.strip():
                        node[key] = wrap(value, 430 if group in ('title', 'titles') else width, advances)
                        if 'credits' in name and key == 'tag0464':
                            node[key] = wrap(value, 400, advances)
            reflow(obj['strings'])
    for text in all_strings(translated):
        for line in text.split('\n'):
            if line and (line[0] in NO_START or line[-1] in NO_END):
                raise ValueError('禁則処理に違反する行があります。')
    source_data = Archive(source / 'data/data.m4b')
    ui_name = 'common/common.m4b/menu/subtitle_ui.bin'
    ui = bytearray(source_data.get(ui_name))
    source_data.f.close()
    if len(ui) != 117 or abs(struct.unpack_from('<f', ui, 51)[0] - .3) > .0001:
        raise ValueError('字幕UIが未対応の形式です。')
    struct.pack_into('<f', ui, 51, .1)
    struct.pack_into('<f', ui, 59, .8)
    glyphs[ui_name] = bytes(ui)
    changes = {'data/data.m4b': glyphs,
               'data/english/data.m4b': {name: serialize(obj) for name, obj in translated.items()},
               'data/patch.m4b': {'english.m4b/' + name: serialize(translated[name]) for name in overrides}}
    manifest = {'format_version': 1, 'patch_revision': PATCH_REVISION,
                'translation_sha256': digest(TRANSLATIONS), 'files': {},
                'subtitle_files': len(load_json(TRANSLATIONS)['subtitles']), 'subtitle_cues': line_count,
                'translated_menu_strings': menu_count, 'fonts': font_stats}
    for name, replacements in changes.items():
        archive = Archive(source / name)
        groups = {}
        for virtual, content in replacements.items():
            if '.m4b/' in virtual:
                prefix, inner = virtual.split('.m4b/', 1)
                groups.setdefault(prefix + '.m4b', {})[inner] = content
            else:
                archive.replace(virtual, content)
        for prefix, items in groups.items():
            child = Archive(archive.get(prefix))
            for virtual, content in items.items():
                child.replace(virtual, content)
            buffer = io.BytesIO()
            child.write(buffer)
            archive.replace(prefix, buffer.getvalue())
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('wb') as stream:
            archive.write(stream)
        archive.f.close()
        check = Archive(target)
        for virtual, content in replacements.items():
            if check.get(virtual) != content:
                raise ValueError(f'生成結果が一致しません: {virtual}')
        check.f.close()
        manifest['files'][name] = {'original': SUPPORTED[name], 'patched': digest(target)}
        print(f'生成済み: {name}', flush=True)
    write_json(output / 'manifest.json', manifest)
    return manifest


def copy_atomic(source, destination):
    temporary = destination.with_name(destination.name + '.ja-new')
    if temporary.exists():
        raise ValueError(f'作業途中のファイルがあります。内容を確認してください: {temporary}')
    try:
        shutil.copy2(source, temporary)
        if digest(temporary) != digest(source):
            raise ValueError(f'コピー内容が一致しません: {temporary}')
        temporary.replace(destination)
    except BaseException:
        if temporary.exists():
            temporary.unlink()
        raise


def install_files(game, built, backup, manifest):
    changed = []
    try:
        for name, info in manifest['files'].items():
            if digest(game / name) == info['patched']:
                continue
            changed.append(name)
            copy_atomic(built / name, game / name)
    except BaseException:
        for name in reversed(changed):
            copy_atomic(backup / name, game / name)
        raise


def read_state(state):
    for name in ['pending.json', 'manifest.json']:
        if (state / name).is_file():
            return load_json(state / name)
    return None


def validate_current(game, state_info):
    if state_info and (state_info.get('format_version') != 1 or set(state_info.get('files', {})) != set(SUPPORTED)):
        raise ValueError('バックアップ管理情報の形式が不正です。')
    for name, original in SUPPORTED.items():
        allowed = {original}
        if state_info:
            if state_info['files'][name]['original'] != original:
                raise ValueError('バックアップ管理情報の原本ハッシュが一致しません。')
            allowed.add(state_info['files'][name]['patched'])
        if not (game / name).is_file() or digest(game / name) not in allowed:
            raise ValueError(f'未対応または管理外の変更があります: {game / name}')


def apply(game, font_path):
    require_stopped()
    state = game / STATE_NAME
    previous = read_state(state)
    validate_current(game, previous)
    if previous and previous.get('patch_revision') == PATCH_REVISION and previous['translation_sha256'] == digest(TRANSLATIONS):
        if all(digest(game / name) == previous['files'][name]['patched'] for name in SUPPORTED):
            validate_originals(state / 'backup')
            print('同じ日本語版が適用済みです。変更はありません。')
            return
    if not font_path.is_file():
        raise ValueError(f'フォントがありません。--font で使用するフォントを指定してください: {font_path}')
    required = sum((game / name).stat().st_size for name in SUPPORTED) * 3 + 512 * 1024 * 1024
    if shutil.disk_usage(game).free < required:
        raise ValueError('作業用の空き容量が不足しています。7 GB以上を目安に空きを確保してください。')
    backup = state / 'backup'
    # All current files have been validated before making the first backup.
    for name, expected in SUPPORTED.items():
        target = backup / name
        if target.exists():
            if digest(target) != expected:
                raise ValueError(f'原本バックアップが一致しません: {target}')
        else:
            if digest(game / name) != expected:
                raise ValueError(f'原本のバックアップがありません: {target}')
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(game / name, target)
    validate_originals(backup)
    built = state / 'build'
    manifest = build(backup, built, font_path)
    require_stopped()
    write_json(state / 'pending.json', manifest)
    install_files(game, built, backup, manifest)
    (state / 'pending.json').replace(state / 'manifest.json')
    print('日本語化の適用が完了しました。Steamの言語は英語のまま、字幕をONにしてください。')


def restore(game):
    require_stopped()
    state = game / STATE_NAME
    manifest = read_state(state)
    if not manifest:
        raise ValueError('この公開版ツールで作成したバックアップがありません。')
    validate_originals(state / 'backup')
    validate_current(game, manifest)
    require_stopped()
    for name, expected in SUPPORTED.items():
        if digest(game / name) != expected:
            copy_atomic(state / 'backup' / name, game / name)
    print('元のアーカイブへ復元しました。セーブ・字幕設定・ウィンドウ設定は変更しません。')


def main():
    if not __debug__:
        raise ValueError('検証を無効化する Python -O オプションには対応していません。')
    parser = argparse.ArgumentParser(description='Myst IV: Revelation 日本語化ツール')
    parser.add_argument('command', choices=['build', 'apply', 'restore', 'verify'])
    parser.add_argument('--game-dir', type=Path)
    parser.add_argument('--font', type=Path, default=Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts/YuGothM.ttc')
    parser.add_argument('--output', type=Path, default=ROOT / 'build')
    args = parser.parse_args()
    game = (args.game_dir or detect_game()).resolve()
    if args.command == 'build':
        if args.output.resolve() == game:
            raise ValueError('出力先をゲーム本体と同じフォルダーにはできません。')
        build(game, args.output.resolve(), args.font)
    elif args.command == 'apply':
        apply(game, args.font)
    elif args.command == 'restore':
        restore(game)
    else:
        state = read_state(game / STATE_NAME)
        if not state:
            raise ValueError('適用情報がありません。')
        validate_originals(game / STATE_NAME / 'backup')
        validate_current(game, state)
        if not all(digest(game / name) == state['files'][name]['patched'] for name in SUPPORTED):
            raise ValueError('日本語版は適用されていません。')
        print('導入済みアーカイブと原本バックアップのハッシュが一致しました。')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, AssertionError, OSError, KeyError, ImportError) as error:
        print(f'エラー: {error}', file=sys.stderr)
        sys.exit(1)
