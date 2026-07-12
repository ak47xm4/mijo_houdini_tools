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
# 【新手導讀 / 這個工具在做什麼】
#
# 情境：你在 Houdini 用 filecache 節點把模擬結果寫到「網路磁碟」(公司共用的網路硬碟)。
#      網路磁碟讀取很慢，會拖慢你在本機的預覽/播放。
#
# 這個工具做的事：
#   1. 把 filecache 已經算好的快取檔，用 robocopy 複製一份到「本機磁碟」(速度快)。
#   2. 自動在旁邊建立一個 file 節點，指到剛剛複製到本機的那份檔案。
#   從此你就用那個 file 節點來預覽，讀取速度快很多。
#   (這種「先把資料抓到本機再用」的做法，靈感來自 Blackmagic Fusion 的 LocalCache。)
#
# 使用方式：在網路(SOP 內)選取一個或多個 filecache 節點，執行本工具即可。
#
# 【第一次用要先設定「本機快取要放哪」】
#   本機路徑「不寫死」在腳本裡，而是每臺機器用「環境變數」各自設定，
#   這樣同一支共用腳本，不同機器(有人 D:、有人 E:)都能用，進 git 也不會互相覆蓋。
#   - 主要變數：MIJO_LOCALCACHE_PATH  = 快取要複製到本機的哪個資料夾(例如 D:/h_cache/)
#   - 次要變數：MIJO_NETCACHE_PATH    = 反向操作(本機→網路)時要放的資料夾，可不設
#   沒設定也沒關係：會自動退回腳本裡的預設值(見下方「手動設定區」)。
#   詳細設定步驟(系統環境變數 / houdini.env 兩種方式)也寫在「手動設定區」的註解裡。
#
# 名詞小抄：
#   - node(節點)  ：Houdini 網路裡的一個方塊，例如 filecache、file。
#   - parm(參數)  ：節點上的欄位，例如 filecache 的 "file" 就是它輸出的檔案路徑。
#   - robocopy    ：Windows 內建的檔案複製指令，適合複製整個資料夾、可多執行緒、可續傳。
#   - 背景/後台複製：複製很花時間，所以丟到背景跑，避免 Houdini 介面卡住不能操作。
##############################################################################################################

##############################################################################################################
# start
# ---- 匯入需要的模組 ----
import os          # 作業系統相關：路徑、建立資料夾、列出檔案
import hou          # Houdini 的 Python API，只有在 Houdini 裡面才有這個模組
import string       # 這裡只用到 string.ascii_uppercase，也就是 'A'~'Z'
import ctypes       # 直接呼叫 Windows 系統 API(判斷磁碟是不是網路磁碟)
import threading    # 開背景執行緒，用來「等 robocopy 跑完」而不卡住 Houdini
import subprocess   # 用來啟動外部程式(robocopy)
from pathlib import Path  # 好用的路徑物件，這裡拿來取得「檔案所在資料夾」

# ---- 手動設定區(想改行為，主要就是改這裡) ----
#
# 【路徑改用「環境變數」控制】
# 每一臺機器/每個 user 的本機磁碟可能都不一樣(有人是 D:、有人是 E:)，
# 所以這裡「優先讀環境變數」，讓每臺機器自己設定，不用去改這支共用腳本；
# 如果讀不到環境變數，才退回使用後面寫死的預設值。
#
# 怎麼設定環境變數(下面兩種方式擇一即可)：
#   方式1) Windows 系統環境變數：新增 MIJO_LOCALCACHE_PATH，值填 D:/h_cache/
#   方式2) Houdini 的 houdini.env 檔加一行： MIJO_LOCALCACHE_PATH = "D:/h_cache/"
# 這裡用 hou.getenv 讀取(第二個參數就是「抓不到時的預設值」)，
# 好處是上面兩種設法(系統環境變數 / houdini.env)都抓得到。

# 當快取原本在「網路磁碟」時，要複製到本機的哪個資料夾：
LocalCache_path = hou.getenv('MIJO_LOCALCACHE_PATH', 'H:/h_cache/')

# 反向操作用的：當快取原本已經在「本機」時，工具會把它放到這個路徑。
# 同樣支援環境變數 MIJO_NETCACHE_PATH，抓不到就用預設值。
# $HIP 是 Houdini 變數，代表目前 hip 檔所在的資料夾。
networkDriverCache_path = hou.getenv('MIJO_NETCACHE_PATH', '$HIP/geo/')

# 保險：把路徑結尾統一補上一個 '/'。
# 因為後面會直接把資料夾名接在這個路徑後面，萬一有人在環境變數忘了加斜線，
# 就會黏成錯的資料夾名(例如 D:/h_cache + H!geo → D:/h_cacheH!geo)。
# rstrip('/') 先去掉尾端所有斜線，再補剛好一個，確保結尾一定是單一個 '/'。
LocalCache_path = LocalCache_path.rstrip('/') + '/'
networkDriverCache_path = networkDriverCache_path.rstrip('/') + '/'

# 本地磁碟改為自動偵測(見 get_local_drivers)。
# 下面這份清單只當「手動補充」用：若某個磁碟被誤判、或你想強制視為本地，加進來即可。
# 統一存成大寫，比較時不分大小寫
localDrivers_manual = []

# start
##############################################################################################################
# functions


DRIVE_REMOTE = 4  # win32 GetDriveType 回傳 4 就代表「網路磁碟」(這是 Windows 定義的常數)


def get_local_drivers():
    # 目的：自動找出電腦上所有「不是網路磁碟」的磁碟代號，回傳像 ['C:', 'D:', 'H:'] 這樣的清單。
    # 之後判斷某個檔案是不是在網路上，就是拿它的磁碟代號來跟這份清單比對。
    # 用 Python 內建的 ctypes 直接呼叫 Windows 系統 API，好處是不用另外安裝 pywin32 套件。
    local = []
    kernel32 = ctypes.windll.kernel32           # 拿到 Windows 核心函式庫的介面
    bitmask = kernel32.GetLogicalDrives()        # 回傳一個「位元遮罩」：第 0 位=A、第 1 位=B... 是 1 代表該代號有掛載
    for i, letter in enumerate(string.ascii_uppercase):  # 逐一檢查 A~Z
        if not (bitmask >> i) & 1:
            continue  # 這個代號沒掛載(該位元是 0)，跳過
        drive_type = kernel32.GetDriveTypeW(letter + ':\\')  # 查這個磁碟是哪種類型(本機硬碟、光碟、網路...)
        if drive_type != DRIVE_REMOTE:
            local.append(letter + ':')  # 只要不是網路磁碟，就當作本機磁碟收進清單
    # 併入使用者手動補充的清單(例如自動判斷失準時可以強制指定)，統一轉大寫方便比較
    local += [d.upper() for d in localDrivers_manual]
    return local


def is_netfile(path):
    # 目的：判斷這個檔案路徑是不是在「網路磁碟」上，回傳 True/False。
    # 先把 Windows 的反斜線 \ 全部換成斜線 /，後面處理起來比較單純。
    path = path.replace('\\', '/')

    # 情況一：UNC 路徑，長得像 //server/share/...，這種一定是網路，直接回 True。
    if path.startswith('//'):
        return True

    # 情況二：一般的磁碟代號路徑，例如 'H:/geo/...'。
    # 取路徑「第一段」(切開後的第一塊，也就是 'H:')當作磁碟代號，
    # 如果它不在剛剛抓到的本機磁碟清單裡，就代表它是網路磁碟。
    first_segment = path.split('/')[0]
    local_drivers = [d.upper() for d in get_local_drivers()]
    return first_segment.upper() not in local_drivers  # 不在本機清單 → 是網路檔


def watch_robocopy(proc, name, log_handle):
    # 這個函式會被丟到「背景執行緒」裡跑(見下方 main 裡的 threading.Thread)。
    # 任務：一直等到 robocopy 這個外部程式跑完，然後看它的結束代碼(exit code)判斷成不成功。
    #
    # 重要觀念：Houdini 的 UI(例如彈出視窗 hou.ui.*)「不是執行緒安全」的，
    #   在背景執行緒裡呼叫會出問題，所以這裡只用 print 印到 console，不彈視窗。
    proc.wait()             # 卡在這行，直到 robocopy 這個程序結束
    if log_handle:
        log_handle.close()  # 關掉 log 檔案(前面是開著寫入的)
    code = proc.returncode  # 取得結束代碼
    # robocopy 的結束代碼有點特別：0~7 都算成功(0=沒東西要複製、1=有複製...等)，
    # 只有 >=8 才是真的出錯。這跟一般程式「0 成功、非 0 失敗」不一樣，別搞混。
    if code >= 8:
        print('!!!! robocopy 失敗 "' + name + '" exit code=' + str(code) +
              '，詳見 _robocopy_log.txt')
    else:
        print(name + '____robocopy 完成 (exit code=' + str(code) + ')')


def build_goal_filename(goal_dir, cfn_split, the_F_expression, is_bgeo_sc):
    # 目的：把「目標資料夾 + 檔名」組合成完整的目標檔案路徑。
    # 檔名通常長這樣：mycache.$F4.bgeo.sc，用 '.' 切開會變成 ['mycache', '$F4', 'bgeo', 'sc']。
    #   cfn_split[0]  = 檔名主體(mycache)
    #   the_F_expression = 幀表達式($F4 之類的)；如果是「單幀緩存」就會是空字串
    #   is_bgeo_sc    = 副檔名是不是 bgeo.sc(它有兩節，要特別處理)
    ext = 'bgeo.sc' if is_bgeo_sc else cfn_split[-1]  # bgeo.sc 特例，否則取最後一段當副檔名

    name_parts = [cfn_split[0]]        # 先放檔名主體
    if the_F_expression:               # 有幀表達式才加(單幀緩存就不加)
        name_parts.append(the_F_expression)
    name_parts.append(ext)             # 最後加上副檔名

    # 用 '.' 把各段接回去，再接在目標資料夾後面。例如：H:/h_cache/xxx/mycache.$F4.bgeo.sc
    return goal_dir + '.'.join(name_parts)


# functions
##############################################################################################################
# process


def main():
    # 主流程：跑過每一個「被選取的」節點，只處理 filecache，其餘略過。
    print("-----------------------------------")

    nodes = hou.selectedNodes()  # 取得使用者目前在網路裡選取的所有節點

    for n in nodes:  # 一個一個處理
        # 只處理 filecache 節點。用「型別名稱開頭是不是 filecache」來判斷，
        # 比去比對節點的字串表示法(repr)更穩，也不會被版本號寫死綁死。
        if not n.type().name().startswith('filecache'):
            continue  # 不是 filecache 就跳過，換下一個

        geo_node = n.parent()  # filecache 的上層(通常是 SOP 的 geo 容器)，等下要在這裡面建 file 節點
        name = str(n.name())   # 這個 filecache 節點的名字

        file_node_Name = ("file_" + name)  # 我們要建立的 file 節點名字，用 file_ 當前綴好辨認

        # 如果同名的 file 節點已經存在(例如你之前跑過一次)，就沿用它；否則新建一個。
        # 這樣重複執行不會一直長出新節點。
        file_node = hou.node(geo_node.path() + '/' + file_node_Name)
        if file_node is None:
            file_node = geo_node.createNode("file", node_name=file_node_Name)

        # filecache 的 "file" 參數就是它輸出的檔案路徑。
        filename = n.parm("file").eval()  # eval() = 把變數/表達式都算成最終的實際路徑字串
        filename_unexpandedString = n.parm(
            "file").unexpandedString()  # 相對地，這是「沒展開」的原始字串，$F、$HIP 都還在 → 用來抓幀表達式

        # 判斷這份快取現在是放在網路磁碟(True)還是本機(False)。
        cache_is_on_netDriver = is_netfile(filename)
        print(file_node_Name + ' == netfile : ' + str(cache_is_on_netDriver))

        # 把新建的 file 節點擺在 filecache 節點右邊一點(+4)，視覺上比較整齊。
        node_pos = n.position()
        file_node.setPosition([node_pos[0] + 4, node_pos[1]])

        # ---- 拆解路徑，取出「資料夾」和「檔名」兩部分 ----
        cache_files_dir = Path(filename).parent.absolute()  # 取得檔案所在的資料夾
        cache_files_dir = str(cache_files_dir)  # 轉成純字串比較好處理
        cache_files_dir = cache_files_dir.replace('\\', '/')  # 反斜線一律換成斜線，避免 Windows 路徑麻煩
        cache_files_name = os.path.basename(filename)  # 只取檔名(不含資料夾)
        cfn_split = cache_files_name.split('.')  # 把「已展開」的檔名依 . 切段
        cfn_split_expandString = filename_unexpandedString.split('.')  # 把「未展開」的原始檔名依 . 切段

        # fusion 風格的重點：用「原始完整資料夾路徑」轉出一個獨一無二的資料夾名，
        # 這樣不同來源的快取複製到本機時不會互相蓋掉。
        #   把 / 換成 !，再把 : 拿掉，例如 'H:/geo/sim' → 'H!geo!sim'
        local_cache_filename_dir = cache_files_dir.replace('/', '!')
        local_cache_filename_dir = local_cache_filename_dir.replace(':', '')

        # 決定「要複製到哪裡」的目標資料夾：
        #   在網路上 → 複製到本機 LocalCache_path
        #   在本機   → 反向複製到 networkDriverCache_path
        if cache_is_on_netDriver:
            goal_cache_file_dir = LocalCache_path + local_cache_filename_dir + '/'
        else:
            goal_cache_file_dir = networkDriverCache_path + local_cache_filename_dir + '/'

        # ---- 找出檔名裡的「幀表達式」($F、$F4、$T 之類) ----
        # 為什麼用未展開字串？因為展開後 $F4 會變成 0001 這種數字，就認不出來了。
        the_F_expression = ''
        for i in cfn_split_expandString:
            if i.startswith('$F'):   # $F、$F4、$FF... 開頭都是 $F
                the_F_expression = i
                break
            if i == '$T':            # $T 是模擬時間的幀變數
                the_F_expression = i
                break

        # 如果整個檔名都找不到 $F/$T，通常代表這是「單幀」快取(只有一個檔，沒有序列)。
        # 這裡只印個提醒，程式仍會照單幀方式繼續處理。
        if not the_F_expression:
            print('    warning : "' + name +
                  '" 沒有 $F/$T 幀表達式，以單幀方式處理')

        # 組出 file 節點要指向的完整目標檔案路徑。
        goal_cache_filename = build_goal_filename(
            goal_cache_file_dir, cfn_split, the_F_expression,
            cache_files_name.endswith('.bgeo.sc'))

        # 把 file 節點的路徑設成上面算好的目標路徑 → 之後就從這個(較快的)位置讀取。
        file_node.parm("file").set(goal_cache_filename)

        # ---- 準備複製：來源(src) 與 目的地(dest) ----
        src = cache_files_dir  # 來源就是原本快取所在的資料夾
        if cache_is_on_netDriver:
            dest = goal_cache_file_dir  # 本機路徑不含 Houdini 變數，直接用
        else:
            # 目的含有 $HIP 這種 Houdini 變數，要先 expandString 展開成真正的路徑
            dest = hou.text.expandString(goal_cache_file_dir)

        # 建立目的資料夾。exist_ok=True 表示「已經存在也不要報錯」。
        os.makedirs(dest, exist_ok=True)

        # 檢查來源資料夾能不能讀。讀不到(例如網路斷線、路徑錯)就跳過這個節點，
        # 並用彈窗提示使用者。
        try:
            os.listdir(src)
        except OSError as e:
            empty_message = '!!!! nothing in "' + name + '" : ' + str(e)
            hou.ui.displayMessage(empty_message)  # 這裡在主執行緒，可以安全彈窗
            print(empty_message)
            continue

        # ---- 組出 robocopy 指令，交給它把整個資料夾複製過去 ----
        # robocopy 是 Windows 指令，路徑要用反斜線，所以再換回 \。
        cmd_copy_src = src.replace('/', '\\')
        cmd_copy_dst = dest.replace('/', '\\')
        # 用 list(串列)方式傳參數比較安全，不用擔心路徑有空白被拆錯。各參數意思：
        #   /MT:8 = 用 8 條執行緒多工複製(比較快)
        #   /XO   = 略過比較舊的檔案(已經是最新就不重複複製，達到「只複製有變動的」)
        #   /NJH /NJS = 不印表頭/表尾摘要   /NC /NS = 不印檔案類別/大小   /NP = 不印百分比進度
        #   (上面這些 /N* 都是為了讓 log 乾淨一點)
        cmd = [
            'robocopy', cmd_copy_src, cmd_copy_dst,
            '/MT:8', '/XO', '/NJH', '/NJS', '/NC', '/NS', '/NP'
        ]

        # 把 robocopy 的輸出寫進 log 檔。
        #   用 'wb'(binary 二進位)開檔，避免中文/編碼造成寫入報錯；
        #   不用 subprocess.PIPE，是因為在背景跑時若沒人即時讀取 PIPE，
        #   緩衝區塞滿會讓 robocopy 卡住不動。寫檔就沒這個問題。
        log_path = os.path.join(cmd_copy_dst, '_robocopy_log.txt')
        try:
            log_handle = open(log_path, 'wb')
            proc = subprocess.Popen(cmd,               # 啟動 robocopy，不等它跑完(非阻塞)
                                    stdout=log_handle,  # 標準輸出寫進 log 檔
                                    stderr=subprocess.STDOUT)  # 錯誤輸出也併進同一個 log
        except OSError as e:
            fail_message = '!!!! robocopy 啟動失敗 "' + name + '" : ' + str(e)
            hou.ui.displayMessage(fail_message)
            print(fail_message)
            continue

        # 開一條背景執行緒去「等這個 robocopy 跑完並回報結果」。
        # daemon=True 表示：就算 Houdini 關掉,這條背景執行緒不會拖著不放。
        watcher = threading.Thread(target=watch_robocopy,
                                   args=(proc, name, log_handle))
        watcher.daemon = True
        watcher.start()

        # 提醒：到這裡 robocopy 其實還在背景複製中，這行只代表「已經開始」，不是「已完成」。
        print(name + "____已在後台開始複製緩存")
        print("-----------------------------------")

    # 迴圈跑完 = 所有選到的 filecache 都已「開始」複製(不代表都複製完了)。
    print("all started , robocopy 仍在後台執行，稍待即可~~~~~~~")


# 這支腳本被 shelf 工具載入(reload)後會直接執行 main()，所以最後直接呼叫它。
main()

# process
