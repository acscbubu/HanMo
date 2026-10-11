"""Host-execute the device /move and /delete handler bodies with fault-injecting HAL.

The JSON parser and path normalizer are the repository's real ArduinoJson and
FsHelpers; only the network and storage edges are faked.
"""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / 'src/network/CrossPointWebServer.cpp'
JSON = ROOT / '.pio/libdeps/x4pro_custom/ArduinoJson/src'


def body(source, signature):
    match = re.search(r'^(?:String|bool|void)\s+' + re.escape(signature) + r'\s*\([^)]*\)\s*(?:const\s*)?\{', source, re.M)
    if not match:
        raise AssertionError(f'Missing production function {signature}')
    start = source.index('{', match.start())
    depth = 0
    for offset in range(start, len(source)):
        if source[offset] == '{':
            depth += 1
        elif source[offset] == '}':
            depth -= 1
            if depth == 0:
                return source[match.start():offset + 1]
    raise AssertionError(f'Unclosed production function {signature}')


STRING_SHIM = r'''
#pragma once
#include <string>
#include <cstring>
#include <cstdint>
class String : public std::string {
public:
 using std::string::string;
 using std::string::operator+=;
 String(const std::string& s):std::string(s){}
 bool isEmpty() const {return empty();}
 bool startsWith(const char* s) const {return rfind(s,0)==0;}
 bool endsWith(const char* s) const {auto n=strlen(s);return size()>=n && compare(size()-n,n,s)==0;}
 bool equals(const char* s) const {return *this==s;}
 int lastIndexOf(char c) const {auto n=rfind(c);return n==npos?-1:static_cast<int>(n);}
 String substring(int start,int end=-1) const {return substr(start,end<0?npos:end-start);}
};
'''

STUB = r'''
#include <WString.h>
#include <ArduinoJson.h>
#include <algorithm>
#include <cassert>
#include <cstring>
#include <map>
#include <memory>
#include <set>
#include <string>
#include <string_view>
#include <vector>
#include <FsHelpers.h>
#define LOG_DBG(...) ((void)0)
#define LOG_ERR(...) ((void)0)
// Match ArduinoJson's built-in Arduino String converter for a host String shim.
void convertFromJson(ArduinoJson::JsonVariantConst src,String& out) {
 auto value=src.as<ArduinoJson::JsonString>();
 if(value) out.assign(value.c_str(),value.size());
 else {std::string serialized;ArduinoJson::serializeJson(src,serialized);out=serialized;}
}
bool canConvertFromJson(ArduinoJson::JsonVariantConst src,const String&) {
 return src.is<ArduinoJson::JsonString>();
}
struct WebServerFake {
 std::map<std::string,String> args;
 int status=0;String message;
 bool hasArg(const char* key) const {return args.count(key)>0;}
 String arg(const char* key) const {return args.at(key);}
 void send(int code,const char*,const String& text) {status=code;message=text;}
};
struct HalFile {
 std::string path;bool valid=false,dir=false;
 explicit operator bool() const {return valid;}
 bool isDirectory() const {return dir;}
 void close(){valid=false;}
 HalFile openNextFile();
 bool rename(const char* dest);
};
struct FakeStorage {
 std::map<std::string,std::string> files;
 std::set<std::string> dirs{"/","/Read","/Archive","/XTCache","/.crosspoint","/System Volume Information"};
 std::string failRemove,failRename;
 int removes=0,renames=0,rmdirs=0;
 bool exists(const char* p) const {return files.count(p)||dirs.count(p);}
 HalFile open(const char* p) const {return {p,exists(p),dirs.count(p)!=0};}
 bool remove(const char* p){++removes;if(failRemove==p)return false;return files.erase(p)!=0;}
 bool rmdir(const char* p){++rmdirs;return dirs.erase(p)!=0;}
 bool rename(const char* a,const char* b){++renames;if(failRename==a||!files.count(a)||exists(b))return false;files[b]=files[a];files.erase(a);return true;}
} Storage;
HalFile HalFile::openNextFile() {
 for (const auto& [name, data]:Storage.files) if(name.rfind(path+"/",0)==0) return {name,true,false};
 for (const auto& name:Storage.dirs) if(name!=path && name.rfind(path+"/",0)==0) return {name,true,true};
 return {};
}
bool HalFile::rename(const char* dest) {return Storage.rename(path.c_str(),dest);}
std::vector<std::string> evictions,artifactMoves,referenceMoves;
bool artifactsOk=true,referencesOk=true;
bool clearBookCache(const std::string& path){evictions.push_back(path);return true;}
bool relocateBookArtifacts(const std::string& oldPath,const std::string& newPath){artifactMoves.push_back(oldPath+" -> "+newPath);return artifactsOk;}
bool relocateBookReferences(const std::string& oldPath,const std::string& newPath){referenceMoves.push_back(oldPath+" -> "+newPath);return referencesOk;}
class CrossPointWebServer {
public:
 std::unique_ptr<WebServerFake> server=std::make_unique<WebServerFake>();
 void handleMove() const;
 void handleDelete() const;
};
'''


class WebFileMutationTest(unittest.TestCase):
    def run_case(self, main):
        source = SERVER.read_text()
        hidden = re.search(r'constexpr const char\* HIDDEN_ITEMS\[\] = [^;]+;', source)
        self.assertIsNotNone(hidden)
        helpers = [body(source, name) for name in ('normalizeWebPath', 'isProtectedItemName')]
        if 'bool isProtectedWebPath(' in source:
            helpers.append(body(source, 'isProtectedWebPath'))
        cpp = ('\n'.join((STUB, 'namespace {', hidden.group(0), *helpers, '}  // namespace',
                          body(source, 'CrossPointWebServer::handleMove'),
                          body(source, 'CrossPointWebServer::handleDelete'),
                          'int main() {', main, '}')))
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            (temp / 'WString.h').write_text(STRING_SHIM)
            src, exe = temp / 'web_file_mutations.cpp', temp / 'web_file_mutations'
            src.write_text(cpp)
            subprocess.run(['g++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            '-fsanitize=undefined', '-fno-omit-frame-pointer',
                            '-I' + str(temp), '-I' + str(JSON), '-I' + str(ROOT / 'lib/FsHelpers'),
                            str(src), str(ROOT / 'lib/FsHelpers/FsHelpers.cpp'), '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True)

    def test_protected_ancestors_reject_move_without_writes_but_read_root_works(self):
        self.run_case(r'''
 Storage.files["/XTCache/child.txt"]="secret";
 Storage.files["/Read/book.txt"]="book";
 Storage.dirs.insert("/XTCache/Sub");
 CrossPointWebServer web;
 web.server->args={{"path","/XTCache/child.txt"},{"dest","/Archive"}};
 web.handleMove();assert(web.server->status==403 && Storage.renames==0 && evictions.empty());
 web.server->args={{"path","/Read/book.txt"},{"dest","/XTCache/Sub"}};
 web.handleMove();assert(web.server->status==403 && Storage.renames==0);
 web.server->args={{"path","/Read/book.txt"},{"dest","/xtcache/Sub"}};
 web.handleMove();assert(web.server->status==403 && Storage.renames==0);
 web.server->args={{"path","/Read/book.txt"},{"dest","/XTCache/../Archive"}};
 web.handleMove();assert(web.server->status==403 && Storage.renames==0);
 web.server->args={{"path","/Read/book.txt"},{"dest","/Archive"}};
 web.handleMove();assert(web.server->status==200 && Storage.files.count("/Archive/book.txt") && Storage.renames==1);
 Storage.files["/Archive/other.txt"]="other";
 web.server->args={{"path","/Archive/other.txt"},{"dest","/"}};
 web.handleMove();assert(web.server->status==200 && Storage.files.count("/other.txt"));
''')


    def test_delete_preflights_all_paths_and_protected_ancestors(self):
        self.run_case(r'''
 Storage.files["/Read/a.txt"]="a";
 Storage.files["/XTCache/child.txt"]="secret";
 CrossPointWebServer web;
 for (const auto& invalid : {R"(["/Read/a.txt",null])", R"(["/Read/a.txt",42])",
                             R"(["/Read/a.txt","/"])", R"(["/Read/a.txt","/XTCache/child.txt"])",
                             R"(["/Read/a.txt","/XTCache/../Read/other.txt"])",
                             R"(["/Read/a.txt","/xtcache/child.txt"])",
                             R"(["/Read/a.txt","/.crosspoint/private.txt"])",
                             R"(["/Read/a.txt","/Read/.hidden/child.txt"])",
                             R"(["/Read/a.txt",{"path":"/Read/b.txt"}])"}) {
   web.server->args={{"paths",invalid}};web.handleDelete();
   assert((web.server->status==400 || web.server->status==403) && Storage.removes==0 && Storage.rmdirs==0);
   assert(Storage.files.count("/Read/a.txt") && evictions.empty());
 }
 web.server->args={{"path","/XTCache/child.txt"}};
 web.handleDelete();assert(web.server->status==403 && Storage.removes==0);
 web.server->args={{"path","Read/a.txt"}};
 web.handleDelete();assert(web.server->status==200 && Storage.removes==1 && !Storage.files.count("/Read/a.txt"));
''')


    def test_move_relocates_book_artifacts_and_references_only_after_successful_rename(self):
        self.run_case(r'''
 Storage.files["/Read/novel.epub"]="book";
 CrossPointWebServer web;
 web.server->args={{"path","/Read/novel.epub"},{"dest","/Archive"}};
 web.handleMove();
 assert(web.server->status==200 && Storage.files.count("/Archive/novel.epub"));
 assert((artifactMoves==std::vector<std::string>{"/Read/novel.epub -> /Archive/novel.epub"}));
 assert(referenceMoves==artifactMoves && evictions.empty());
 Storage.files["/Read/failed.txt"]="still here";Storage.failRename="/Read/failed.txt";
 web.server->args={{"path","/Read/failed.txt"},{"dest","/Archive"}};
 web.handleMove();assert(web.server->status==500 && Storage.files.count("/Read/failed.txt"));
 assert(artifactMoves.size()==1 && referenceMoves.size()==1 && evictions.empty());
 Storage.failRename="";Storage.files["/Read/partial.txt"]="book";
 artifactsOk=false;referencesOk=false;
 web.server->args={{"path","/Read/partial.txt"},{"dest","/Archive"}};
 web.handleMove();
 assert(web.server->status==500 && Storage.files.count("/Archive/partial.txt"));
 assert(artifactMoves.size()==2 && referenceMoves.size()==2 && evictions.empty());
''')


    def test_delete_evicts_only_after_successful_remove_with_valid_io_partial_failure(self):
        self.run_case(r'''
 Storage.files["/Read/one.epub"]="one";
 Storage.files["/Read/two.epub"]="two";
 Storage.failRemove="/Read/two.epub";
 CrossPointWebServer web;
 web.server->args={{"paths",R"(["/Read/one.epub","/Read/two.epub"])"}};
 web.handleDelete();
 assert(web.server->status==500 && Storage.removes==2 && !Storage.files.count("/Read/one.epub"));
 assert(Storage.files.count("/Read/two.epub"));
 assert((evictions==std::vector<std::string>{"/Read/one.epub"}));
 web.server->args={{"path","/Read/two.epub"}};
 web.handleDelete();
 assert(web.server->status==500 && Storage.files.count("/Read/two.epub") && evictions.size()==1);
''')


    def test_rejects_embedded_nul_and_empty_destination_before_any_write(self):
        self.run_case(r'''
 Storage.files["/Read/a.txt"]="a";Storage.files["/Read/b.txt"]="b";
 CrossPointWebServer web;
 web.server->args={{"paths",R"(["/Read/a.txt","/Read/b.txt\u0000hidden"])"}};
 web.handleDelete();
 assert(web.server->status==400 && Storage.removes==0 && evictions.empty());
 web.server->args={{"path",String(std::string("/Read/a.txt")+'\0'+"suffix")},{"dest","/Archive"}};
 web.handleMove();assert(web.server->status==400 && Storage.renames==0);
 web.server->args={{"path","/Read/a.txt"},{"dest",String(std::string("/Archive")+'\0'+"suffix")}};
 web.handleMove();assert(web.server->status==400 && Storage.renames==0);
 web.server->args={{"path","/Read/a.txt"},{"dest",""}};
 web.handleMove();assert(web.server->status==400 && Storage.renames==0);
 assert(Storage.files.count("/Read/a.txt") && Storage.files.count("/Read/b.txt"));
''')


if __name__ == '__main__':
    unittest.main()
