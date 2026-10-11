#!/usr/bin/env python3
"""MIT License. Copyright (c) 2026 HanMo contributors.
Assemble the published X4 Pro FULL from pinned components; never accesses USB.
"""
import argparse,hashlib,json,struct,zlib
from pathlib import Path

def sha(b): return hashlib.sha256(b).hexdigest()
def esp(b):
 assert len(b)>=24 and b[0]==0xe9 and 1<=b[1]<=16
 assert struct.unpack_from('<H',b,12)[0]==9,'ESP32-S3 required'
 p=24;checksum=0xef
 for _ in range(b[1]):
  assert p+8<=len(b);size=struct.unpack_from('<I',b,p+4)[0];p+=8
  assert p+size<=len(b)
  for c in b[p:p+size]:checksum^=c
  p+=size
 end=((p+1+15)//16)*16
 assert end<=len(b) and b[end-1]==checksum
 if b[23]:assert b[23]==1 and b[end:end+32]==hashlib.sha256(b[:end]).digest();end+=32
 return end

def assemble(app):
 root=Path(__file__).resolve().parent
 m=json.loads((root/'FULL-MANIFEST.json').read_text('utf8'))
 for name,meta in m['files'].items():
  b=(root/name).read_bytes();assert len(b)==meta['bytes'] and sha(b)==meta['sha256'],name
 a=app.read_bytes();assert len(a)==m['application']['bytes'] and sha(a)==m['application']['sha256'],'Wrong UPDATE'
 assert esp(a)==len(a)
 boot=(root/'bootloader.bin').read_bytes();assert esp(boot)==len(boot)<0x8000
 pt=(root/'partitions.bin').read_bytes()
 parts=[];i=0
 while pt[i:i+2]==b'\xaa\x50':
  magic,t,sub,off,size,label,flags=struct.unpack_from('<HBBII16sI',pt,i)
  parts.append((t,sub,off,size,label.rstrip(b'\0').decode(),flags));i+=32
 assert pt[i:i+2]==b'\xeb\xeb' and pt[i+16:i+32]==hashlib.md5(pt[:i]).digest(),'Partition table MD5'
 assert [(p[4],p[2],p[3]) for p in parts]==[('nvs',0x9000,0x5000),('otadata',0xe000,0x2000),('app0',0x10000,0x7f0000),('app1',0x800000,0x7f0000),('coredump',0xff0000,0x10000)]
 ot=(root/'boot_app0.bin').read_bytes();valid=[]
 for off in [0,0x1000]:
  seq=struct.unpack_from('<I',ot,off)[0];crc=struct.unpack_from('<I',ot,off+28)[0]
  if seq not in [0,0xffffffff] and crc==(zlib.crc32(ot[off:off+4],0xffffffff)&0xffffffff):valid.append(seq)
 assert valid and (max(valid)-1)%2==0,'Must boot app0'
 blobs=[(0,boot),(0x8000,pt),(0xe000,ot),(0x10000,a)]
 for (off,b),(nxt,_) in zip(blobs,blobs[1:]): assert off+len(b)<=nxt
 assert len(a)<=0x7f0000
 full=bytearray(b'\xff'*m['totalBytes'])
 for off,b in blobs:full[off:off+len(b)]=b
 assert full[0x9000:0xe000]==b'\xff'*0x5000
 assert full[0x800000:]==b'\xff'*0x800000
 assert full[0x10000:0x10000+len(a)]==a
 return full

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--app',type=Path,required=True);p.add_argument('--out',type=Path,required=True);args=p.parse_args()
 data=assemble(args.app)
 with args.out.open('xb') as f:f.write(data)
 print(json.dumps({'name':args.out.name,'bytes':len(data),'sha256':sha(data),'app0EqualsUpdate':True,'nvsBlank':True,'app1AndCoredumpBlank':True,'initialBootSlot':0}))
