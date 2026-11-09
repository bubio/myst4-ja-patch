"""Local Ubisoft M4B and length-prefixed text formats; no game assets included."""
import io
import struct

def name(value):
    encoded = value.encode('ascii') + b'\0'
    return struct.pack('<I', len(encoded)) + encoded

class Archive:
    def __init__(self, source):
        self.f = io.BytesIO(source) if isinstance(source, bytes) else open(source, 'rb')
        self.f.seek(0)
        assert self.read_name() == 'UBI_BF_SIG'
        assert self.uint() == 1 and self.uint() == 0
        self.root = self.folder()
    def uint(self): return struct.unpack('<I', self.f.read(4))[0]
    def read_name(self):
        b = self.f.read(self.uint()); assert b[-1] == 0
        return b[:-1].decode('ascii')
    def folder(self):
        dirs, files = {}, {}
        for _ in range(self.f.read(1)[0]):
            key = self.read_name(); dirs[key] = self.folder()
        for _ in range(self.uint()):
            key = self.read_name(); size, off = self.uint(), self.uint()
            files[key] = {'size': size, 'offset': off, 'data': None}
        return {'dirs': dirs, 'files': files}
    def read_file(self, entry):
        if entry['data'] is not None: return entry['data']
        self.f.seek(entry['offset']); b = self.f.read(entry['size'])
        assert len(b) == entry['size']; return b
    def replace(self, path, data):
        parts = path.split('/'); node = self.root
        for i, part in enumerate(parts[:-1]):
            if part.endswith('.m4b'):
                child = Archive(self.read_file(node['files'][part]))
                child.replace('/'.join(parts[i+1:]), data)
                buf = io.BytesIO(); child.write(buf)
                node['files'][part] = {'size': len(buf.getvalue()), 'offset': 0, 'data': buf.getvalue()}
                return
            node = node['dirs'].setdefault(part, {'dirs': {}, 'files': {}})
        node['files'][parts[-1]] = {'size': len(data), 'offset': 0, 'data': data}
    def get(self, path):
        parts = path.split('/'); node = self.root
        for i, part in enumerate(parts[:-1]):
            if part.endswith('.m4b'):
                return Archive(self.read_file(node['files'][part])).get('/'.join(parts[i+1:]))
            node = node['dirs'][part]
        return self.read_file(node['files'][parts[-1]])
    def write(self, out):
        entries = []
        def toc(node, start):
            b = bytes([len(node['dirs'])])
            for k, v in node['dirs'].items(): b += name(k) + toc(v, start)
            b += u(len(node['files']))
            for k, e in node['files'].items():
                off = start[0]; start[0] += e['size']
                b += name(k) + u(e['size']) + u(off)
                entries.append(e)
            return b
        header = name('UBI_BF_SIG') + u(1) + u(0)
        directory = toc(self.root, [0]); entries.clear()
        directory = toc(self.root, [len(header)+len(directory)])
        out.write(header + directory)
        for e in entries:
            if e['data'] is not None: out.write(e['data']); continue
            self.f.seek(e['offset']); remaining = e['size']
            while remaining:
                b = self.f.read(min(1024*1024, remaining)); assert b
                out.write(b); remaining -= len(b)

class Reader:
    def __init__(self,b):self.b=b;self.p=8
    def take(self,n):
        b=self.b[self.p:self.p+n];self.p+=n;assert len(b)==n;return b
    def uint(self):return struct.unpack('<I',self.take(4))[0]
    def string(self):return self.take(self.uint()).decode('ascii')
    def wide(self):return self.take(2*self.uint()).decode('utf-16-le')
    def tree(self):
        nv,nc=self.uint(),self.uint();d={}
        for _ in range(nv):k=self.string();assert k not in d;d[k]=self.wide()
        for _ in range(nc):k=self.string();assert k not in d;d[k]=self.tree()
        return d
    def read(self,subtitle):
        assert self.b[:8]==b'ubi/b0-l';version=self.uint();assert self.uint()==1
        kind=self.take(self.uint()).hex();assert self.uint()==1
        if subtitle:
            sound=self.string();lines=[]
            for _ in range(self.uint()):
                a,z=struct.unpack('<ff',self.take(8));lines.append({'start':a,'end':z,'text':self.wide()})
            result={'lines':lines,'sound':sound}
        else:result={'strings':self.tree()}
        assert self.p==len(self.b)
        return version,kind,result

def u(n):
    return struct.pack('<I', n)

def s(value):
    b = value.encode('ascii')
    return u(len(b)) + b

def w(value):
    b = value.encode('utf-16-le')
    return u(len(b) // 2) + b

def tree(values):
    leaves = [(k, v) for k, v in values.items() if isinstance(v, str)]
    children = [(k, v) for k, v in values.items() if isinstance(v, dict)]
    return (u(len(leaves)) + u(len(children))
            + b''.join(s(k) + w(v) for k, v in leaves)
            + b''.join(s(k) + tree(v) for k, v in children))

def serialize(obj):
    kind = bytes.fromhex(obj['type_hex'])
    b = b'ubi/b0-l' + u(obj['version']) + u(1) + u(len(kind)) + kind + u(1)
    if 'lines' in obj:
        b += s(obj['sound']) + u(len(obj['lines']))
        for line in obj['lines']:
            b += struct.pack('<ff', line['start'], line['end']) + w(line['text'])
    else:
        b += tree(obj['strings'])
    return b

def parse_text(data, subtitle):
    version, kind, body = Reader(data).read(subtitle)
    return {"version": version, "type_hex": kind, **body}

def list_files(archive, prefix="", node=None):
    node = archive.root if node is None else node
    for name in node["files"]:
        yield prefix + name
    for name, child in node["dirs"].items():
        yield from list_files(archive, prefix + name + "/", child)
