#!/usr/bin/python

import sys, getopt, shlex, json, subprocess, os.path, time, re
from copy import deepcopy
from time import sleep


# global variable for adb path
path = './adb.exe'

# Error code
NO_ADB    = 1
WRONG_OPT = 2
NO_DEVICE = 3


# Formatter for realtime output
# printf("%5s %-8s %2s %3s %4s %1s %5s %7s %7s %3s %s\n", "PID", "USER", "PR", "NI", "CPU%", "S", "#THR", "VSS", "RSS", "PCY", "Name");
# PID, CPU%, VSS, VSS%, ROM%, BATTERY%, NAME
row_formatter = '{:>5}{:>7}{:>10}{:>8.2%}{:>8}{:>8.2%}{:>10}  {}'
header_formatter = '{:>5}{:>7}{:>10}{:>8}{:>8}{:>8}{:>10}  {}'
header = header_formatter.format('PID', 'CPU%', 'RSS', 'RSS%', 'ROM', 'ROM%', 'BATTERY%', 'NAME')


# Regular expressions
regex_package_name = re.compile(r'\[(.*?)\]')
regex_data_path = re.compile(r'=(.*)')
# regex_app_name = re.compile(r'^com(\.[\w]+)+$')


pagesize = 4096 # in Bytes

# Json Structure
data = {}
stat = {
    'name': '',
    'time': [],
    'cpu': [],
    'ram_p': [],  # ram in percentage
    'ram_t': [],  # total ram in MB
    'rom_p': [],  # rom in percentage
    'rom_t': [],  # total rom in MB
    'battery': []
}



def getCmdOutput(cmd):
    args = shlex.split(cmd)
    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    return p.communicate()[0]


def deviceConnected():
    cmd = path + ' devices'
    out = getCmdOutput(cmd)
    return len(out.split('\n')) > 1


def getPidList():
    cmd = path + ' shell ls proc'
    out = getCmdOutput(cmd)
    pidList = [pid for pid in out.split() if pid.isdigit()]
    return pidList


def getCmdline(pid):
    cmd = path + ' shell cat proc/' + pid + '/cmdline'
    out = getCmdOutput(cmd)
    return out.strip('\0')


def getStat(pid = ''):
    cmd = path + ' shell cat proc/' + pid + '/stat'
    out = getCmdOutput(cmd)
    return out.split()


def programExists(prog_name):
    cmd = path + ' shell which ' + prog_name
    out = getCmdOutput(cmd)
    return out

def getStatFromTop(args):
    cmd = path + ' shell top ' + args
    out = getCmdOutput(cmd)
    if (len(out) > 4):
        return out.splitlines()[4:]
    else:
        return []

def runAsRoot():
    cmd = path + ' root'
    getCmdOutput(cmd)


def getMemInfo():
    cmd = path + ' shell cat proc/meminfo'
    out = getCmdOutput(cmd)
    return out.split()


def getRom(app_path):
    cmd = path + ' shell du -s ' + app_path
    out = getCmdOutput(cmd)
    if out: return int(out.split()[0])
    else: return 0


def getDiskStats():
    cmd = path + ' shell dumpsys diskstats'
    out = getCmdOutput(cmd)
    line = ''
    if out: line = out.splitlines()[1].split()
    return line

# Not implemented
def getBattery(pid):
    return 0


def isApp(app_name):
    return len(app_name) >= 4 and app_name[:4] == 'com.'


# Usage function if-else statement for more cases
def exitWithMsg(err_code = WRONG_OPT):
    if err_code == NO_ADB:
        print ('Could not find adb')
    elif err_code == NO_DEVICE:
        print ('Could not find android device')
    else: # default
        print ('Usage: ')
        print (sys.argv[0] + ' <interval_time(ms)> [-rpo]')
        print ()
        print ('-r <running_time>, --rtime <running_time>          - Total running time(s). The program will not stop')
        print ('                                                     running if running_time is unspecified.')
        print ('-p <adb_path>, --path <adb_path>                   - The path of adb excutable. The adb excutable')
        print ('                                                     will be searched in the current folder if the')
        print ('                                                     is unspecified.')
        print ('-o <output_path>, --output <output_path>           - The path of output file. Instead of saving the')
        print ('                                                     result in the output file, the result will be')
        print ('                                                     printed in the terminal if the output paht is')
        print ('                                                     unspecified.')

    sys.exit(err_code)




def main(argv):
    interval = 0
    running = 0
    keep_running = True
    interrupt = False
    outfile = None
    write_file = False
    use_top = False

    try:
        opts, *_ = getopt.getopt(argv[1:],"r:p:o:",["rtime=","path=","output="])
    except getopt.GetoptError as err:
        # print (str(err))
        exitWithMsg()

    if not (argv and argv[0].isdigit()):
        exitWithMsg()

    for opt, arg in opts:
        if opt in ("-r", "--rtime"):
            keep_running = False
            running = arg
        elif opt in ("-p", "--path"):
            global path
            path = arg
        elif opt in ("-o", "--output"):
            write_file = True
            outfile = arg


    ############## Verify ADB and Connection ##############
    if not os.path.exists(path):
        exitWithMsg(NO_ADB)

    if not deviceConnected():
        exitWithMsg(NO_DEVICE)


    #################### Shell Commands ###################
    cmd_top = shlex.split(path + ' shell top -n 2 -d 1')
    cmd_packages = shlex.split(path + ' shell dumpsys package -f p')


    ##################### Preparation #####################
    if len(programExists('top')):
        print ('Found top command')
        use_top = True
    else:
        print ('Could not find top command')


    cpu_user = 0

    interval = int(argv[0]) / 1000.0
    running = float(running)
    elapsed_time = 0.0


    # Package Info
    print ('Reading package information...')

    package_paths = {}

    # Get ouput from dumpsys command
    p = subprocess.Popen(cmd_packages, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

    while True:
        output = p.stdout.readline()
        if output == '' and p.poll() is not None:
            break
        if output.startswith('  Package '):
            package_name = ''
            found = regex_package_name.search(output)
            if found: package_name = found.group(1)
            if not isApp(package_name): continue
            while True:
                output = p.stdout.readline()
                if output == '' and p.poll() is not None:
                    break
                if output.startswith('    dataDir='):
                    found = regex_data_path.search(output)
                    if found:
                        package_paths[package_name] = found.group(1)
                        break

    return_code = p.poll()
    if return_code != 0:
        pass

    use_top = False # disable top currently
    cnt = 0  # iteration counter

    # One more round for reading proc
    if not use_top:
        elapsed_time -= interval
        cnt = -1
    
    # utime, ntime, stime, itime
    old_cpu_time = None
    new_cpu_time = None
    # utime, stime
    old_pid_stat = {}
    new_pid_stat = {}

    # all about animation
    animation = '|/-\\'
    animation_idx = 0

    while (not interrupt and (keep_running or elapsed_time <= running)):       
        try:
            iteration_start_time = time.process_time()
        
            # iterations
            # print (cnt)
            cnt += 1

            # Memory Info
            memInfo = getMemInfo()
            mem_tot = float(memInfo[1])
            mem_free = float(memInfo[4])
            mem_used = mem_tot - mem_free            

            # Storage Info
            diskinfo = getDiskStats()
            sto_free = float(diskinfo[1][:-1])
            sto_tot = float(diskinfo[3][:-1])
            sto_used = sto_tot - sto_free


            if use_top:
                p = subprocess.Popen(cmd_top, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
                line_cnt = 0
                header_cnt = 0
                return_code = 0
            else:
                pid_list = getPidList()
                pid_size = len(pid_list)
                pid_idx = 0
                if elapsed_time < 0.0:
                    old_cpu_time = [float(t) for t in getStat()[1:5]]
                else:
                    new_cpu_time = [float(t) for t in getStat()[1:5]]
                    # (new_cpu_utime + new_cpu_ntime) - (old_cpu_utime + old_cpu_ntime)
                    cpu_user_time = sum([x - y for x, y in zip(new_cpu_time[:2], old_cpu_time[:2])])
                    
                    # new_cpu_utime + new_cpu_ntime + new_cpu_stime + new_cpu_itime)
                    # - (old_cpu_utime + old_cpu_ntime + old_cpu_stime + old_cpu_itime)
                    total_delta_time = sum([x - y for x, y in zip(new_cpu_time, old_cpu_time)])

                    cpu_user = round(cpu_user_time * 1.0 / total_delta_time)

            proc_result = '' # for terminal display

            # Extracting data
            while True:
                pid = ''
                name = ''
                cpu = 0
                ram_pct = 0
                ram_tot = 0
                rom_pct = 0
                rom_tot = 0
                battery = 0

                if use_top:
                    output = p.stdout.readline()

                    if output == '' and p.poll() is not None:
                        break

                    if len(output) >= 4 and output[:4] == 'User':
                        header_cnt += 1

                    if (header_cnt < 3):
                        continue

                    line_cnt += 1

                    # skip headers
                    if line_cnt < 4:
                        continue

                    line = output.split()
                    
                    name = line[10]
                    # Skip process's name not start with com.
                    if not isApp(name):
                        continue

                    pid = line[0]   
                    cpu = int(line[4][:-1])
                    ram_tot = int(line[8][:-1])
                else:
                    if (pid_idx >= pid_size): break
                    pid = pid_list[pid_idx]
                    pid_idx += 1
                    # Filter processes
                    name = getCmdline(pid)
                    if not isApp(name):
                        continue

                    # initial pid_stat list
                    if pid not in old_pid_stat:
                        pid_stat = getStat(pid)
                        if pid_stat:
                            old_pid_stat[pid] = pid_stat
                        continue
                    new_pid_stat[pid] = getStat(pid)

                    if new_pid_stat[pid] and pid in old_pid_stat:
                        delta_time = float(new_pid_stat[pid][13]) + float(new_pid_stat[pid][14]) - float(old_pid_stat[pid][13]) - float(old_pid_stat[pid][14])
                        cpu = delta_time * 100 / total_delta_time
                        cpu = int(round(cpu))
                        ram_tot = int(new_pid_stat[pid][23]) * pagesize / 1024.0

                # Ram and Rom
                ram_pct = ram_tot / mem_tot
                ram_tot /= 1024.0 # convert to MB
                if name in package_paths: rom = getRom(package_paths[name])
                rom_pct = rom_tot / sto_tot
                rom_tot /= 1024.0 # convert to MB


                if write_file:
                    if '0' not in data:
                        data['0'] = deepcopy(stat)
                        data['0']['name'] = 'System'

                    if pid not in data:
                        # print (pid + ': ' + str(len(pid_stat)))
                        data[pid] = deepcopy(stat)
                        data[pid]['name'] = name
                    data[pid]['time'].append(elapsed_time)
                    data[pid]['cpu'].append(cpu)
                    data[pid]['ram_p'].append(round(ram_pct, 2))
                    data[pid]['ram_t'].append(round(ram_tot, 2))
                    data[pid]['rom_p'].append(round(rom_pct, 2))
                    data[pid]['rom_t'].append(round(rom_tot, 2))
                    data[pid]['battery'].append(battery) # placeholder
                elif use_top or new_pid_stat:
                    proc_result += row_formatter.format(pid, str(cpu) + '%', '{:.2f}M'.format(ram_tot), ram_pct, '{:.2f}M'.format(rom_tot), rom_pct, battery, name)  + '\n'


            if use_top:
                return_code = p.poll()
                if return_code != 0:
                    pass
            else:
                if new_cpu_time:
                    old_cpu_time = new_cpu_time
                if new_pid_stat:
                    old_pid_stat = new_pid_stat


            if not write_file and proc_result:
                subprocess.call('cls' if os.name == 'nt' else 'clear', shell = True)
                print (header +  '                 Iteration: ' + str(cnt))
                total = row_formatter.format('0', str(cpu_user) + '%', '{:.2f}M'.format(mem_tot / 1024), mem_used / mem_tot, '{:.2f}M'.format(sto_tot / 1024), sto_used / sto_tot, battery, 'System')  + '\n'
                proc_result = total + proc_result
                print (proc_result[:-1])
                print ('Press ctrl + c to stop...')
            elif write_file and '0' in data:
                data['0']['time'].append(elapsed_time)
                data['0']['cpu'].append(cpu_user)
                data['0']['ram_p'].append(round(mem_used / mem_tot, 2))
                data['0']['ram_t'].append(round(mem_tot / 1024, 2))
                data['0']['rom_p'].append(round(sto_used / sto_tot, 2))
                data['0']['rom_t'].append(round(sto_tot / 1024, 2))
                data['0']['battery'].append(battery) # placeholder

                sys.stdout.write('Press ctrl + c to stop sampling and save result to ' + outfile + ' ' + animation[animation_idx % len(animation)] + '\r')
                animation_idx += 1

            elapsed_time += interval

            time_cost = time.process_time() - iteration_start_time
            # if cnt > 0: print (time_cost) # for debugging
            if (time_cost < interval):
                sleep(interval - time_cost)

        # use ctrl+c to stop infinite loop
        except KeyboardInterrupt:
            interrupt = True
        finally:
            pass

    # Write JSON to file
    # print(json.dumps(data, separators=(',', ':'), sort_keys = True))
    if write_file:
        sys.stdout.write('\n')
        with open(outfile, 'w') as ofile:
            json.dump(data, ofile, separators=(',', ':'), sort_keys = True)


if __name__ == "__main__":
    main(sys.argv[1:])




# Android Top Implementation
# http://androidxref.com/7.0.0_r1/xref/system/core/toolbox/top.c

# Proc Manual
# http://man7.org/linux/man-pages/man5/proc.5.html

# Android data storage
# https://www.liaohuqiu.net/cn/posts/storage-in-android/