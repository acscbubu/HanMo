"""Real sockets + source-matched mbedTLS engine; not ESP32 hardware validation."""
from pathlib import Path
import subprocess,ssl,socket,threading,json,datetime,tempfile
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import ec
import argparse
ap=argparse.ArgumentParser();ap.add_argument('--work-dir',type=Path,required=True);ap.add_argument('--client',type=Path,required=True);args=ap.parse_args()
W=args.work_dir.resolve();W.mkdir(parents=True,exist_ok=True);P=Path(__file__).resolve().parents[1]
if W==P or W.is_relative_to(P):raise SystemExit('Keep disposable test certificates outside the source package.')
D=W/'tls-test-private';D.mkdir(exist_ok=True)
now=datetime.datetime.now(datetime.timezone.utc)
def key():return ec.generate_private_key(ec.SECP256R1())
ca=key();name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'HanMo disposable test CA')])
def cert(subject,pub,issuer,k,start,end,ca=False,san=None):
 b=x509.CertificateBuilder().subject_name(subject).issuer_name(issuer).public_key(pub).serial_number(x509.random_serial_number()).not_valid_before(start).not_valid_after(end).add_extension(x509.BasicConstraints(ca=ca,path_length=None),True)
 if san:b=b.add_extension(x509.SubjectAlternativeName([x509.DNSName(san)]),False)
 return b.sign(k,hashes.SHA256())
def savecert(n,c):p=D/(n+'.pem');p.write_bytes(c.public_bytes(serialization.Encoding.PEM));return p
root=savecert('ca',cert(name,ca.public_key(),name,ca,now-datetime.timedelta(days=1),now+datetime.timedelta(days=30),True))
leaves={}
for n,san,lo,hi in [('valid','localhost',-1,2),('expired','localhost',-3,-2),('future','localhost',2,3),('wronghost','other.test',-1,2)]:
 k=key();p=D/(n+'.key');p.write_bytes(k.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
 c=savecert(n,cert(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,san)]),k.public_key(),name,ca,now+datetime.timedelta(days=lo),now+datetime.timedelta(days=hi),san=san));leaves[n]=(c,p)
results=[]
for version in [ssl.TLSVersion.TLSv1_2,ssl.TLSVersion.TLSv1_3]:
 for case in ['valid','expired','future','wronghost','untrusted']:
  ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);ctx.minimum_version=version;ctx.maximum_version=version
  ctx.load_cert_chain(*leaves['valid' if case=='untrusted' else case])
  listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen();listener.settimeout(8);port=listener.getsockname()[1]
  server={}
  def serve():
   try:
    raw,_=listener.accept();raw.settimeout(5)
    with ctx.wrap_socket(raw,server_side=True) as conn:
     server['version']=conn.version();conn.recv(4096);conn.sendall(b'HTTP/1.0 200 OK\r\nContent-Length: 2\r\n\r\nOK')
   except (ssl.SSLError,OSError) as e:server['error']=type(e).__name__
   finally:listener.close()
  th=threading.Thread(target=serve);th.start()
  cmd=[str(args.client.resolve()),'server_name=localhost','server_addr=127.0.0.1',f'server_port={port}','auth_mode=required','ca_file='+('none' if case=='untrusted' else str(root)),'read_timeout=3000','force_version='+('tls12' if version==ssl.TLSVersion.TLSv1_2 else 'tls13')]
  p=subprocess.run(cmd,text=True,capture_output=True,timeout=12);th.join(9)
  log=p.stdout+p.stderr;(D/f'{version.name}-{case}.log').write_text(log)
  success=p.returncode==0 and '200 OK' in log
  assert success==(case=='valid'),(case,version,p.returncode,log[-2500:])
  if case!='valid':assert 'certificate' in log.lower() or 'ca_chain' in log,log
  results.append({'tls':version.name,'case':case,'exit':p.returncode,'accepted':success,'server':server})
out={'scope':'Real localhost sockets, OpenSSL server, mbedTLS 3.6.5 source-matched host build. Host default crypto configuration; NOT ESP32 adapter/hardware execution. Disposable test keys remain outside source delivery.','results':results}
(W/'tls-engine-results.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
