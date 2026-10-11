// QA-only wall-clock override. No source or simulator code is replaced.
#define _GNU_SOURCE
#include <stdlib.h>
#include <stdio.h>
#include <time.h>
#include <dlfcn.h>
time_t time(time_t* out) {
 const char* path=getenv("HANMO_QA_EPOCH_FILE");
 time_t value;
 if(path){FILE* f=fopen(path,"r");long long n=0;if(!f||fscanf(f,"%lld",&n)!=1)abort();fclose(f);value=(time_t)n;}
 else{time_t(*real_time)(time_t*)=dlsym(RTLD_NEXT,"time");value=real_time(NULL);}
 if(out)*out=value;
 return value;
}
