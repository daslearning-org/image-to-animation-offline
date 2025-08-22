## Build
```bash
ls /home/somnath/codes/git/my-org/dascafe/mobileApps/.env/lib/python3.9/site-packages/numpy/core/include/numpy/ndarrayobject.h

export LDFLAGS=""
export LINKFORSHARED=""

source /home/somnath/codes/git/my-org/dascafe/mobileApps/.env/bin/activate

buildozer android clean
buildozer -v android debug
```