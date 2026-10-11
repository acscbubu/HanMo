from pathlib import Path
import subprocess,json
import argparse
ap=argparse.ArgumentParser();ap.add_argument('--work-dir',type=Path,required=True);args=ap.parse_args()
W=args.work_dir.resolve();W.mkdir(parents=True,exist_ok=True);P=Path(__file__).resolve().parents[1];N=P/'hanmo/freeink-sdk/libs/network/SecureNet'
T=W/'transport-test';T.mkdir(exist_ok=True)
(T/'psa').mkdir(exist_ok=True);(T/'mbedtls').mkdir(exist_ok=True)
(T/'psa/crypto.h').write_text('inline int psa_crypto_init(){return 0;}\n#define PSA_SUCCESS 0\n')
(T/'mbedtls/build_info.h').write_text('#define CONFIG_MBEDTLS_SSL_PROTO_TLS1_3 1\n#define CONFIG_MBEDTLS_HAVE_TIME_DATE 1\n')
(T/'Arduino.h').write_text('''#pragma once
#include <string>
#include <cstdint>
#include <cstring>
#include <memory>
#include <vector>
#include <algorithm>
#include <time.h>
using String=std::string;
inline unsigned long tick=0;
inline unsigned long millis(){return ++tick;}
inline void delay(unsigned long ms){tick+=ms;}
#define log_e(...) ((void)0)
class IPAddress { public: String toString(){return "127.0.0.1";} };
class Client { public:
 virtual ~Client()=default;
 virtual int connect(const char*,uint16_t)=0; virtual int connect(IPAddress,uint16_t)=0;
 virtual size_t write(const uint8_t*,size_t)=0;
 virtual int read(uint8_t*,size_t)=0; virtual int read(){uint8_t c;return read(&c,1)==1?c:-1;}
 virtual void stop()=0;virtual uint8_t connected()=0;virtual int available()=0;
 unsigned long _timeout=1000;void setTimeout(unsigned long n){_timeout=n;}unsigned long getTimeout(){return _timeout;}
};
inline std::vector<std::string> replies,requests;
inline int connects=0;inline bool forceFail=false;
class WiFiClient:public Client {
 std::string input;size_t pos=0;bool live=false;int index=-1;
 public:
 void setConnectionTimeout(uint32_t){}
 int connect(IPAddress,uint16_t)override{return connect("ip",443);}
 int connect(const char*,uint16_t)override{++connects;if(forceFail)return 0;live=true;index=requests.size();requests.push_back("");return 1;}
 size_t write(const uint8_t* b,size_t n)override{requests.at(index).append((const char*)b,n);if(input.empty()&&!replies.empty()){input=replies.front();replies.erase(replies.begin());pos=0;}return n;}
 int read(uint8_t*b,size_t n)override{if(pos==input.size()){live=false;return 0;}n=std::min(n,input.size()-pos);memcpy(b,input.data()+pos,n);pos+=n;return n;}
 int read()override{return Client::read();}
 int available()override{return input.size()-pos;}
 uint8_t connected()override{return live;}
 void stop()override{live=false;input.clear();pos=0;}
};
''')
(T/'WiFiClient.h').write_text('#include "Arduino.h"\n')
(T/'base64.h').write_text('#include "Arduino.h"\nnamespace base64 {inline String encode(const char*){return "TEST_CREDENTIAL";}}\n')
(T/'NetworkClientSecure.h').write_text('''#pragma once
#include "Arduino.h"
struct Context{bool attached=false;};
inline void attach_ssl_certificate_bundle(Context* c,bool v){c->attached=v;}
class NetworkClientSecure:public WiFiClient {
 protected:
 std::shared_ptr<Context> sslclient=std::make_shared<Context>();
 bool _use_insecure=false,_use_ca_bundle=false;const char* ca=nullptr;
 public:
 void setCACert(const char* p){ca=p;}
 void setInsecure(){_use_insecure=true;}
 void setHandshakeTimeout(unsigned long){}
 void stop()override{WiFiClient::stop();sslclient->attached=false;}
 int connect(const char*h,uint16_t p)override{if(_use_insecure||(!ca&&(!sslclient->attached||!_use_ca_bundle)))return 0;return WiFiClient::connect(h,p);}
 int connect(const char*h,uint16_t p,int32_t t){_timeout=t;return connect(h,p);}
 int connect(IPAddress ip,uint16_t p)override{return WiFiClient::connect(ip,p);}
};
''')
(T/'test.cpp').write_text('''#include <SecureHttpClient.h>
#include <cassert>
#include <iostream>
time_t clockValue=1800000000;
extern "C" time_t time(time_t* p) noexcept {if(p)*p=clockValue;return clockValue;}
void reset(){requests.clear();replies.clear();connects=0;forceFail=false;tick=0;}
std::string response(int status,const std::string& extra="",const std::string& body="OK"){
 return "HTTP/1.1 "+std::to_string(status)+" Test\\r\\nConnection: close\\r\\nContent-Length: "+std::to_string(body.size())+"\\r\\n"+extra+"\\r\\n"+body;
}
int main(){
 int cases=0;
 {reset();freeink::SecureClient c;assert(c.connect("one.test",443));c.stop();assert(c.connect("one.test",443));assert(connects==2);++cases;}
 {reset();freeink::SecureClient c;clockValue=0;assert(!c.connect("one.test",443));assert(connects==0);clockValue=1800000000;++cases;}
 {reset();freeink::SecureClient c;c.setCACert("TEST PEM");assert(c.connect("one.test",443));c.setCACert(nullptr);assert(c.connect("one.test",443));++cases;}
 {reset();forceFail=true;freeink::SecureClient c;assert(!c.connect("one.test",443));assert(connects==1);++cases;}
 {reset();replies={response(200)};freeink::SecureHttpClient h;assert(h.begin("https://one.test/a"));assert(h.GET()==200);assert(h.responseComplete()&&h.getString()=="OK");++cases;}
 {reset();replies={response(302,"Location: http://one.test/b\\r\\n")};freeink::SecureHttpClient h;h.setFollowRedirects(3);h.begin("https://one.test/a");assert(h.GET()==302&&requests.size()==1);++cases;}
 {reset();replies={response(302,"Location: https://two.test/b\\r\\n"),response(200)};freeink::SecureHttpClient h;h.setFollowRedirects(3);h.begin("https://one.test/a");h.setBasicAuth("test","pass");h.addHeader("Cookie","secret");h.addHeader("aUtHoRiZaTiOn","secret");assert(h.GET()==200&&requests.size()==2);assert(requests[0].find("secret")!=std::string::npos);assert(requests[1].find("secret")==std::string::npos&&requests[1].find("TEST_CREDENTIAL")==std::string::npos);++cases;}
 {reset();replies={response(302,"Location: /b\\r\\n"),response(200)};freeink::SecureHttpClient h;h.setFollowRedirects(3);h.begin("https://one.test/a");h.setBasicAuth("test","pass");assert(h.GET()==200&&requests.size()==2);assert(requests[1].find("TEST_CREDENTIAL")!=std::string::npos);++cases;}
 {reset();replies={response(307,"Location: https://two.test/b\\r\\n")};freeink::SecureHttpClient h;h.setFollowRedirects(3);h.begin("https://one.test/a");assert(h.POST("secret")==307&&requests.size()==1);++cases;}
 {reset();replies={"HTTP/1.1 200 OK\\r\\nConnection: close\\r\\nTransfer-Encoding: chunked\\r\\n\\r\\n2\\r\\nOK\\r\\n0\\r\\n\\r\\n"};freeink::SecureHttpClient h;h.begin("https://one.test/a");assert(h.GET()==200&&h.responseComplete()&&h.getString()=="OK");++cases;}
 {reset();replies={"HTTP/1.1 200 OK\\r\\nConnection: close\\r\\nContent-Length: 5\\r\\n\\r\\nOK"};freeink::SecureHttpClient h;h.begin("https://one.test/a");assert(h.GET()==200&&!h.responseComplete());++cases;}
 {reset();replies={response(200)};freeink::SecureHttpClient h;h.begin("https://one.test/a");assert(h.GET([](const uint8_t*,size_t){return false;})==200&&h.callbackAborted());++cases;}
 {reset();freeink::SecureHttpClient h;h.begin("https://one.test/a");assert(h.GET([](const uint8_t*,size_t){return true;},[]{return true;})<0&&h.aborted()&&connects==0);++cases;}
 {reset();replies={response(302,"Location: /b\\r\\n"),response(302,"Location: /c\\r\\n")};freeink::SecureHttpClient h;h.setFollowRedirects(1);h.begin("https://one.test/a");assert(h.GET()==302&&requests.size()==2);++cases;}
 std::cout<<cases<<" production adapter/HTTP policy cases passed (transport stub)\\n";
}
''')
subprocess.run(['g++','-std=c++20','-Wall','-Wextra','-Werror','-I'+str(T),'-I'+str(N/'include'),str(T/'test.cpp'),str(N/'src/SecureClient.cpp'),'-o',str(T/'test')],check=True)
p=subprocess.run([str(T/'test')],capture_output=True,text=True,check=True);print(p.stdout)
(W/'transport-test-result.json').write_text(json.dumps({'result':p.stdout.strip(),'scope':'Actual SecureClient.cpp and SecureHttpClient.h with Arduino/network transport stubs; complements real mbedTLS engine socket tests; not device execution.'},indent=2))
