# fusion style houdini local cache
# by mijo
'''

roadmap:
    efficent to use , preview
##################################################################
future features :
    easy to define where is copy to
        now is using LocalCache_path to define

    smart to know where is copy from
        now is using localDrivers to define

    create comment to record
        copy time?
        the time at copy

    compare difference
    to not copy same file

    use take to control
        switch netDriver and local
        efficent to use , preview
        network render farm friendly

    work with pdg

done features :
    #OK+WIP# local to network  and  network to local
    #OK+WIP# more speed more performance
    #OK+WIP# copy in BG
    #OK+WIP# 單幀(無 $F/$T)緩存 fallback
    #OK+WIP# robocopy 改用 list 參數，不再依賴 shell

features 20221119 :
    copy filecache files to local
    and create file node to read cache

    in blackmagic fusion style OTZ

features 20221127 :
    function is_netfile
    more speed more performance
    copy in BG

features 20221203 :
    manual define local driver
    copy in BG
    $F $F4 $T exprssion solved

features 20240929 :
    robocopy
    copy in BG
##################################################################

not slove yet:
    manual define local driver
    or
    use win32 module

    just support
        $F $FF $F2~?
        $T
        now

##################################################################
test env:
    houdini 19.5.368
    qlib
    labs

    windows 10 21H2

video (tutorial?) :
https://www.youtube.com/watch?v=ukIjS8A3gsQ

'''

##############################################################################################################
# start
import os
import hou
import string
import ctypes
import threading
import subprocess
from pathlib import Path

# manual define
LocalCache_path = 'H:/h_cache/'
networkDriverCache_path = '$HIP/geo/'

# 本地磁碟改為自動偵測(見 get_local_drivers)。
# 下面這份清單只當「手動補充」用：若某個磁碟被誤判、或你想強制視為本地，加進來即可。
# 統一存成大寫，比較時不分大小寫
localDrivers_manual = []

# start
##############################################################################################################
# functions


DRIVE_REMOTE = 4  # win32 GetDriveType：網路磁碟


def get_local_drivers():
    # 自動偵測所有「非網路」磁碟代號(大寫含冒號)，如 ['C:', 'D:', 'H:']
    # 用內建 ctypes 呼叫 Win32 API，不需要 pywin32
    local = []
    kernel32 = ctypes.windll.kernel32
    bitmask = kernel32.GetLogicalDrives()
    for i, letter in enumerate(string.ascii_uppercase):
        if not (bitmask >> i) & 1:
            continue  # 這個代號沒掛載，跳過
        drive_type = kernel32.GetDriveTypeW(letter + ':\\')
        if drive_type != DRIVE_REMOTE:
            local.append(letter + ':')
    # 併入手動補充清單
    local += [d.upper() for d in localDrivers_manual]
    return local


def is_netfile(path):
    # 判斷路徑是否落在網路磁碟上
    path = path.replace('\\', '/')

    # UNC 路徑 //server/share 直接視為網路
    if path.startswith('//'):
        return True

    # 取路徑第一段(磁碟代號)，不在本地清單內即視為網路
    first_segment = path.split('/')[0]
    local_drivers = [d.upper() for d in get_local_drivers()]
    return first_segment.upper() not in local_drivers


def watch_robocopy(proc, name, log_handle):
    # 背景執行緒：等 robocopy 結束並檢查 exit code。
    # 注意：不在此執行緒呼叫 hou.ui.*，Houdini UI 非執行緒安全，只印到 console。
    proc.wait()
    if log_handle:
        log_handle.close()
    code = proc.returncode
    # robocopy exit code：0~7 視為成功(含未變更/已複製)，>=8 為失敗
    if code >= 8:
        print('!!!! robocopy 失敗 "' + name + '" exit code=' + str(code) +
              '，詳見 _robocopy_log.txt')
    else:
        print(name + '____robocopy 完成 (exit code=' + str(code) + ')')


def build_goal_filename(goal_dir, cfn_split, the_F_expression, is_bgeo_sc):
    # 組合目標檔名，若沒有 $F/$T 幀表達式則省略幀段（處理單幀緩存）
    ext = 'bgeo.sc' if is_bgeo_sc else cfn_split[-1]

    name_parts = [cfn_split[0]]
    if the_F_expression:
        name_parts.append(the_F_expression)
    name_parts.append(ext)

    return goal_dir + '.'.join(name_parts)


# functions
##############################################################################################################
# process


def main():
    print("-----------------------------------")

    nodes = hou.selectedNodes()

    for n in nodes:
        # 用節點型別名稱判斷，避免寫死 repr 字串與版本號
        if not n.type().name().startswith('filecache'):
            continue

        geo_node = n.parent()  # sop geo
        name = str(n.name())

        file_node_Name = ("file_" + name)

        # 若同名 file 節點已存在則沿用，否則新建
        file_node = hou.node(geo_node.path() + '/' + file_node_Name)
        if file_node is None:
            file_node = geo_node.createNode("file", node_name=file_node_Name)

        filename = n.parm("file").eval()  # eval file cache path
        filename_unexpandedString = n.parm(
            "file").unexpandedString()  # 未展開的原始字串

        # test network driver
        cache_is_on_netDriver = is_netfile(filename)
        print(file_node_Name + ' == netfile : ' + str(cache_is_on_netDriver))

        # node position
        node_pos = n.position()
        file_node.setPosition([node_pos[0] + 4, node_pos[1]])

        cache_files_dir = Path(filename).parent.absolute()  # get dir folder path
        cache_files_dir = str(cache_files_dir)  # for safe
        cache_files_dir = cache_files_dir.replace('\\', '/')  # fuck \
        cache_files_name = os.path.basename(filename)  # get file name
        cfn_split = cache_files_name.split('.')  # 檔名依 . 切段
        cfn_split_expandString = filename_unexpandedString.split('.')

        # fusion style local cache : 用原始路徑做出唯一的資料夾名
        local_cache_filename_dir = cache_files_dir.replace('/', '!')
        local_cache_filename_dir = local_cache_filename_dir.replace(':', '')

        if cache_is_on_netDriver:
            goal_cache_file_dir = LocalCache_path + local_cache_filename_dir + '/'
        else:
            goal_cache_file_dir = networkDriverCache_path + local_cache_filename_dir + '/'

        # get $F rule
        the_F_expression = ''
        for i in cfn_split_expandString:
            if i.startswith('$F'):
                the_F_expression = i
                break
            if i == '$T':
                the_F_expression = i
                break

        # 若沒抓到 $F/$T，代表可能是單幀緩存，提示一下（仍會照單幀處理）
        if not the_F_expression:
            print('    warning : "' + name +
                  '" 沒有 $F/$T 幀表達式，以單幀方式處理')

        goal_cache_filename = build_goal_filename(
            goal_cache_file_dir, cfn_split, the_F_expression,
            cache_files_name.endswith('.bgeo.sc'))

        # set file node file parm
        file_node.parm("file").set(goal_cache_filename)

        # path to copy files
        src = cache_files_dir
        if cache_is_on_netDriver:
            dest = goal_cache_file_dir
        else:
            dest = hou.text.expandString(goal_cache_file_dir)

        # create folder（已存在也不報錯）
        os.makedirs(dest, exist_ok=True)

        # check empty ? 來源資料夾讀不到就跳過這個節點
        try:
            os.listdir(src)
        except OSError as e:
            empty_message = '!!!! nothing in "' + name + '" : ' + str(e)
            hou.ui.displayMessage(empty_message)
            print(empty_message)
            continue

        # copy files : robocopy 後台複製整個資料夾
        cmd_copy_src = src.replace('/', '\\')
        cmd_copy_dst = dest.replace('/', '\\')
        cmd = [
            'robocopy', cmd_copy_src, cmd_copy_dst,
            '/MT:8', '/XO', '/NJH', '/NJS', '/NC', '/NS', '/NP'
        ]

        # robocopy 輸出寫到 log 檔（用 binary，避免編碼問題；
        # 不用 PIPE，避免輸出把緩衝塞滿導致後台 robocopy 卡住）
        log_path = os.path.join(cmd_copy_dst, '_robocopy_log.txt')
        try:
            log_handle = open(log_path, 'wb')
            proc = subprocess.Popen(cmd,
                                    stdout=log_handle,
                                    stderr=subprocess.STDOUT)
        except OSError as e:
            fail_message = '!!!! robocopy 啟動失敗 "' + name + '" : ' + str(e)
            hou.ui.displayMessage(fail_message)
            print(fail_message)
            continue

        # 背景執行緒監看結束狀態與 exit code（不阻塞 UI）
        watcher = threading.Thread(target=watch_robocopy,
                                   args=(proc, name, log_handle))
        watcher.daemon = True
        watcher.start()

        # 注意：robocopy 仍在後台執行，這裡只是「已開始」而非「已完成」
        print(name + "____已在後台開始複製緩存")
        print("-----------------------------------")

    print("all started , robocopy 仍在後台執行，稍待即可~~~~~~~")


main()

# process
