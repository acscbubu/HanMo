// Independent historical JSP2 fixture; never use the new encoder to make v2.
#pragma once
#include <array>
#include <cstdint>
#include <vector>
namespace basic30fixture {
inline constexpr char v2[]="/.crosspoint/japanese-sentences-v2.bin";
inline constexpr char v2bak[]="/.crosspoint/japanese-sentences-v2.bin.bak";
inline constexpr char v2part[]="/.crosspoint/japanese-sentences-v2.bin.part";
inline uint32_t crc(const uint8_t* p,size_t n){
 uint32_t c=0xffffffffu;
 for(size_t i=0;i<n;++i){c^=p[i];for(int j=0;j<8;++j)c=(c>>1)^(0xedb88320u & (0u-(c&1u)));}
 return ~c;
}
inline void put(uint8_t* p,uint32_t v,int n){for(int i=0;i<n;++i)p[i]=uint8_t(v>>(8*i));}
inline std::vector<uint8_t> v2Bytes(int mode=0){
 std::vector<uint8_t> b(104,0);b[0]='J';b[1]='S';b[2]='P';b[3]='2';
 b[4]=2;b[5]=9;b[6]=6;b[7]=54;b[8]=7;b[9]=1;
 put(b.data()+10,104,2);put(b.data()+12,0x4a534401u,4);put(b.data()+16,91,4);b[20]=8;
 for(int c=0;c<9;++c){b[21+c]=uint8_t(c%6);b[37+c]=uint8_t(c);}
 for(int n=0;n<54;++n){b[46+n]=uint8_t(n);if(mode==0 || n%3==1)b[30+n/8]|=uint8_t(1u<<(n%8));}
 put(b.data()+100,crc(b.data(),100),4);return b;
}
inline void fixV2Crc(std::vector<uint8_t>& b){put(b.data()+100,crc(b.data(),100),4);}
} // namespace basic30fixture
