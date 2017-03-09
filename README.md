# Android Performance Monitor
The program monitors CPU, Memory, Rom and Battery status of an android device.

### Requirements
* Python3
* Android SDK ADB
* Android Phone or Emulator

### Installing
No need to install. 

### Usage
```
android_monitor.py <interval_time(ms)> [-rpo]
-r <running_time>, --rtime <running_time>          
-p <adb_path>, --path <adb_path>                   
-o <output_path>, --output <output_path>           
```

### Examples
Non-stop running and updating status of CPU, Memory, Rom and Battery every 1000(ms) in console:
```
python android_monitor.py 1000 
```
Run for 10 seconds and update every 2000(ms):
```
python android_monitor.py 2000 -r 10 
```
Run with specified adb path:
```
ptyhon android_monitor.py 1000 -p sdk/adb -r 20 
```
Run with specified output path. The result will be saved in *out.json* in following case:
```
python android_monitor.py 1000 -o out.json 
```

### Testing
The program is only tested on Windows 10 with Emulator (*Nexus 6* installed with *Android 7.0*).

### Issues
There are two ways to retrieve system status via adb:
1. Parsing proc filesystem:
It's every inefficient to open a new process and read information via adb many times. Retrieving needed information from proc for all processes every iteration takes 0.5 second in average. 
2. Parsing result from top command
This is way faster than parsing proc, but the interval of the program must be a integer in second, in other words it must be a multiple of 1000. Because```top -n 1``` only gives us cumulative result of processes, we need at least two updates of ```top```to get current status of process. ```top -n 2 -d 1``` is used to collect accurate result if ```top``` command is enabled.
Another issue of using ```top``` command is that sometimes ```top``` returns empty result(haven't figure out why). Parsing result from ```top``` result has been disabled in the code currently.
3. Battery function for apps is not implemented yet.


Conclusion:
Set update interval time at least 1000(ms) to get better result.

### Author

**Ren Wan**  
[Android Performance Monitor](https://github.com/PurpleBooth)
