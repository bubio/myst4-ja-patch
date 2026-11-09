import hashlib
import io
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import patch
from formats import Archive, parse_text, serialize
from fonts import NO_END, NO_START, wrap


def empty_archive():
    return struct.pack('<I', 11) + b'UBI_BF_SIG\0' + struct.pack('<II', 1, 0) + b'\0' + struct.pack('<I', 0)


def to_bytes(archive):
    buffer = io.BytesIO()
    archive.write(buffer)
    return buffer.getvalue()


class FormatTests(unittest.TestCase):
    def test_nested_replacement_preserves_unrelated_content(self):
        child = Archive(empty_archive())
        child.replace('text/subtitle.bin', b'before')
        child.replace('other/image.dat', b'keep nested')
        outer = Archive(empty_archive())
        outer.replace('world/inner.m4b', to_bytes(child))
        outer.replace('sound.dat', b'keep outer')
        loaded = Archive(to_bytes(outer))
        loaded.replace('world/inner.m4b/text/subtitle.bin', b'after')
        loaded.replace('world/inner.m4b/font/new.dat', b'new glyph page')
        result = Archive(to_bytes(loaded))
        self.assertEqual(result.get('world/inner.m4b/text/subtitle.bin'), b'after')
        self.assertEqual(result.get('world/inner.m4b/other/image.dat'), b'keep nested')
        self.assertEqual(result.get('sound.dat'), b'keep outer')
        self.assertEqual(result.get('world/inner.m4b/font/new.dat'), b'new glyph page')

    def test_utf16_subtitle_roundtrip_keeps_times_and_empty_cues(self):
        value = {'version': 36, 'type_hex': '010203', 'sound': 'test.sound',
                 'lines': [{'start': 0., 'end': 1.5, 'text': ''},
                           {'start': 1.5, 'end': 3., 'text': '日本語\n𠮷'}]}
        self.assertEqual(parse_text(serialize(value), True), value)

    def test_menu_tree_and_placeholders_roundtrip(self):
        value = {'version': 37, 'type_hex': '010203',
                 'strings': {'title': {'title': '保存'}, 'labels': {'slot': '保存 %d', 'empty': ''}}}
        self.assertEqual(parse_text(serialize(value), False), value)

    def test_truncated_file_is_rejected(self):
        with self.assertRaises((AssertionError, struct.error)):
            Archive(empty_archive()[:-2])


class TranslationTests(unittest.TestCase):
    def test_catalog_is_complete_and_has_no_original_english_fields(self):
        payload = patch.load_json(patch.TRANSLATIONS)
        self.assertEqual(set(payload), {'format_version', 'subtitles', 'menus'})
        self.assertEqual(len(payload['subtitles']), 240)
        self.assertEqual(sum(map(len, payload['subtitles'].values())), 1118)
        self.assertEqual(sum(map(len, payload['menus'].values())), 443)
        for rows in payload['subtitles'].values():
            self.assertTrue(all(any(ord(c) > 127 for c in t) for t in rows.values()))

    def test_missing_subtitle_is_rejected_instead_of_silently_left_in_english(self):
        original = {'test/subtitle/a.bin': {'lines': [{'text': 'Hello'}]}}
        data = {'format_version': 1, 'subtitles': {'test/subtitle/a.bin': {}}, 'menus': {}}
        with self.assertRaises(ValueError):
            patch.translate(original, data)

    def test_missing_format_placeholder_is_rejected(self):
        original = {'test/text/a.bin': {'strings': {'slot': 'Save %d'}}}
        data = {'format_version': 1, 'subtitles': {}, 'menus': {'test/text/a.bin': {'slot': '保存'}}}
        with self.assertRaises(ValueError):
            patch.translate(original, data)

    def test_japanese_wrapping_preserves_content_and_kinsoku(self):
        text = '「あいうえお」、かきくけこ。さしすせそ。'
        widths = {c: 10 for c in text}
        result = wrap(text, 70, widths)
        self.assertEqual(result.replace('\n', ''), text)
        for line in result.splitlines():
            self.assertLessEqual(sum(widths[c] for c in line), 70)
            self.assertNotIn(line[0], NO_START)
            self.assertNotIn(line[-1], NO_END)


class InstallationTests(unittest.TestCase):
    def test_restore_is_repeatable_and_preserves_saved_games(self):
        with tempfile.TemporaryDirectory() as folder:
            game = Path(folder)
            name = 'data/test.bin'
            original, patched = b'original game', b'Japanese game'
            expected = {name: hashlib.sha256(original).hexdigest()}
            (game / 'data').mkdir()
            (game / name).write_bytes(patched)
            backup = game / patch.STATE_NAME / 'backup' / name
            backup.parent.mkdir(parents=True)
            backup.write_bytes(original)
            (game / 'save').mkdir()
            saved = game / 'save/user-save.m4s'
            saved.write_bytes(b'keep my progress')
            patch.write_json(game / patch.STATE_NAME / 'manifest.json', {
                'format_version': 1, 'files': {name: {'original': expected[name],
                'patched': hashlib.sha256(patched).hexdigest()}}})
            with mock.patch.object(patch, 'SUPPORTED', expected), mock.patch.object(patch, 'require_stopped'):
                patch.restore(game)
                self.assertEqual((game / name).read_bytes(), original)
                with mock.patch.object(patch, 'copy_atomic') as copier:
                    patch.restore(game)
                    copier.assert_not_called()
            self.assertEqual(saved.read_bytes(), b'keep my progress')

    def test_already_applied_version_does_not_rebuild_or_copy(self):
        with tempfile.TemporaryDirectory() as folder:
            game = Path(folder)
            name = 'data/test.bin'
            original, patched = b'original', b'Japanese'
            expected = {name: hashlib.sha256(original).hexdigest()}
            (game / 'data').mkdir()
            (game / name).write_bytes(patched)
            backup = game / patch.STATE_NAME / 'backup' / name
            backup.parent.mkdir(parents=True)
            backup.write_bytes(original)
            patch.write_json(game / patch.STATE_NAME / 'manifest.json', {
                'format_version': 1, 'patch_revision': patch.PATCH_REVISION,
                'translation_sha256': patch.digest(patch.TRANSLATIONS),
                'files': {name: {'original': expected[name], 'patched': hashlib.sha256(patched).hexdigest()}}})
            with mock.patch.object(patch, 'SUPPORTED', expected), mock.patch.object(patch, 'require_stopped'), \
                    mock.patch.object(patch, 'build') as builder, mock.patch.object(patch, 'copy_atomic') as copier:
                patch.apply(game, game / 'not-needed.ttf')
                builder.assert_not_called()
                copier.assert_not_called()

    def test_failed_second_copy_restores_all_changed_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            game, built, backup = (root / p for p in ['game', 'built', 'backup'])
            manifest = {'files': {}}
            for name in ['data/first.bin', 'data/second.bin', 'data/third.bin']:
                for directory, text in [(game, b'original'), (backup, b'original'), (built, b'patched')]:
                    (directory / name).parent.mkdir(parents=True, exist_ok=True)
                    (directory / name).write_bytes(text)
                manifest['files'][name] = {'patched': patch.digest(built / name)}
            actual_copy = patch.copy_atomic
            def fail_second(source, destination):
                if source == built / 'data/second.bin':
                    raise OSError('simulated failure')
                actual_copy(source, destination)
            with mock.patch.object(patch, 'copy_atomic', side_effect=fail_second):
                with self.assertRaises(OSError):
                    patch.install_files(game, built, backup, manifest)
            for name in manifest['files']:
                self.assertEqual((game / name).read_bytes(), b'original')

    def test_unknown_game_data_is_rejected_before_creating_backup(self):
        with tempfile.TemporaryDirectory() as folder:
            game = Path(folder)
            (game / 'data').mkdir()
            target = game / 'data/test.bin'
            target.write_bytes(b'user modification')
            expected = {'data/test.bin': hashlib.sha256(b'original').hexdigest()}
            with mock.patch.object(patch, 'SUPPORTED', expected), mock.patch.object(patch, 'require_stopped'):
                with self.assertRaises(ValueError):
                    patch.apply(game, game / 'missing-font.ttf')
            self.assertEqual(target.read_bytes(), b'user modification')
            self.assertFalse((game / patch.STATE_NAME).exists())

    def test_interrupted_copy_does_not_leave_temp_file_blocking_rollback(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, destination = root / 'source', root / 'destination'
            source.write_bytes(b'new')
            destination.write_bytes(b'original')
            def partial_copy(src, dst):
                Path(dst).write_bytes(b'partial')
                raise OSError('disk full')
            with mock.patch.object(patch.shutil, 'copy2', side_effect=partial_copy):
                with self.assertRaises(OSError):
                    patch.copy_atomic(source, destination)
            self.assertFalse(destination.with_name(destination.name + '.ja-new').exists())
            self.assertEqual(destination.read_bytes(), b'original')


if __name__ == '__main__':
    unittest.main()
