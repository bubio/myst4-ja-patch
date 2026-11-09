"""Generate additional glyph pages from an installed, user-selected font."""
import io
import math
import struct
from pathlib import Path
from formats import u
from PIL import Image, ImageDraw, ImageFont

NO_START = set('、。，．・：；？！ー々ぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮ）］｝〉》」』】〕〗〙〛’”')
NO_END = set('（［｛〈《「『【〔〖〘〚‘“')

def wrap(text, width, advances):
    def measure(s): return sum(advances[c] for c in s)
    output=[]
    for paragraph in text.split('\n'):
        rest=paragraph.strip()
        if not rest: output.append('');continue
        while measure(rest)>width:
            j=0; used=0
            while j<len(rest) and used+advances[rest[j]]<=width:
                used+=advances[rest[j]];j+=1
            assert j>0,rest
            # Prefer sentence/clause boundaries in the latter part of the line.
            choices=[i for i in range(max(1,j*3//5),j+1) if rest[i-1] in '。！？、 ']
            if choices:j=choices[-1]
            while j>1 and (rest[j] in NO_START or rest[j-1] in NO_END):j-=1
            # Avoid dividing Latin words if there is a suitable earlier space.
            if rest[j-1].isascii() and rest[j].isascii() and rest[j-1].isalnum() and rest[j].isalnum():
                space=rest.rfind(' ',max(0,j//3),j)
                if space>0:j=space+1
            line=rest[:j].rstrip();rest=rest[j:].lstrip()
            assert line and measure(line)<=width+.01
            output.append(line)
        output.append(rest)
    return '\n'.join(output)

def font_cmap(font_path):
    # Read the selected TTC face's Unicode cmap to reject missing glyphs.
    raw=Path(font_path).read_bytes()
    base=struct.unpack_from('>I',raw,12)[0] if raw[:4]==b'ttcf' else 0
    count=struct.unpack_from('>H',raw,base+4)[0]
    tables={}
    for i in range(count):
        tag,_,offset,length=struct.unpack_from('>4sIII',raw,base+12+i*16)
        tables[tag]=(offset,length)
    cmap=tables[b'cmap'][0];n=struct.unpack_from('>H',raw,cmap+2)[0];result={}
    for i in range(n):
        platform,encoding,offset=struct.unpack_from('>HHI',raw,cmap+4+i*8)
        if platform not in (0,3):continue
        p=cmap+offset;fmt=struct.unpack_from('>H',raw,p)[0]
        if fmt==12:
            ng=struct.unpack_from('>I',raw,p+12)[0]
            for j in range(ng):
                first,last,glyph=struct.unpack_from('>III',raw,p+16+j*12)
                for cp in range(first,last+1):result[cp]=glyph+cp-first
        elif fmt==4:
            seg=struct.unpack_from('>H',raw,p+6)[0]//2
            ends=struct.unpack_from('>'+'H'*seg,raw,p+14)
            starts=struct.unpack_from('>'+'H'*seg,raw,p+16+2*seg)
            deltas=struct.unpack_from('>'+'h'*seg,raw,p+16+4*seg)
            ro=p+16+6*seg
            for j in range(seg):
                delta=deltas[j];rng=struct.unpack_from('>H',raw,ro+j*2)[0]
                for cp in range(starts[j],ends[j]+1):
                    if cp==0xffff:continue
                    if rng:
                        g=struct.unpack_from('>H',raw,ro+j*2+rng+2*(cp-starts[j]))[0]
                        if g:g=(g+delta)&0xffff
                    else:g=(cp+delta)&0xffff
                    if g:result.setdefault(cp,g)
    return result

def build_fonts(chars, src, font_path):
    changes={};stats=[];advances={}
    cmap=font_cmap(font_path)
    for stem in ['revelation_18','courier new 22']:
        path='common/common.m4b/font/'+stem+'.fnt';original=src.get(path)
        pages,count=struct.unpack_from('<II',original,36)
        records=[struct.unpack_from('<HffffI',original,44+22*i) for i in range(count)]
        existing={r[0] for r in records}
        added=sorted(c for c in chars if ord(c) not in existing and c not in '\n\r\t')
        missing=[c for c in added if not cmap.get(ord(c))]
        assert not missing,('Missing source font glyphs',missing)
        height=round((records[0][4]-records[0][2])*256)
        font=ImageFont.truetype(str(font_path),22 if stem=='revelation_18' else 24)
        per_page=8*(256//height)
        if stem=='revelation_18':
            advances.update({chr(r[0]):round((r[3]-r[1])*256) for r in records})
        for page_index in range(math.ceil(len(added)/per_page)):
            im=Image.new('L',(256,256),0);draw=ImageDraw.Draw(im)
            for i,char in enumerate(added[page_index*per_page:(page_index+1)*per_page]):
                x=(i%8)*32;y=(i//8)*height
                width=min(31,round(draw.textlength(char,font=font))+2)
                box=draw.textbbox((0,0),char,font=font)
                assert box[2]-box[0]<=30 and box[3]-box[1]<=height
                draw.text((x+1-box[0],y+(height-(box[3]-box[1]))//2-box[1]),char,font=font,fill=255)
                records.append((ord(char),x/256,1-(y+height)/256,(x+width)/256,1-y/256,pages+page_index))
                if stem=='revelation_18':advances[char]=width
            pal=Image.new('P',im.size);pal.putpalette([v for i in range(256) for v in (i,i,i)])
            pal.putdata(list(im.get_flattened_data()));buf=io.BytesIO();pal.save(buf,format='TGA')
            changes['common/common.m4b/font/'+stem+f'_{pages+page_index+1:02}.tga']=buf.getvalue()
        records.sort(key=lambda r:r[0])
        assert len({r[0] for r in records})==len(records)
        changes[path]=original[:36]+u(pages+math.ceil(len(added)/per_page))+u(len(records))+b''.join(struct.pack('<HffffI',*r) for r in records)
        stats.append({'font':stem,'glyphs':len(records),'added':len(added),'pages':pages+math.ceil(len(added)/per_page)})
    advances['\n']=0;advances['\r']=0;advances['\t']=advances[' ']*4
    return changes,advances,stats
