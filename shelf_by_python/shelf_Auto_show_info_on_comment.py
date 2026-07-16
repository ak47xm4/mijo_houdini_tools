# auto show info on node comment
# by mijo

'''
roadmap:
    click and show the node info I want

features 20221120 :
    ROP:
        fetch

features 20260717 :
    #OK# 型別判斷改用 type().name()，不再比對 repr 字串
    #OK# 支援多種節點(filecache / file / alembic / ROP 各種 render node ...)
    #OK# 即時更新：參數一改，comment 自動跟著改(hou.node.addEventCallback)
    #OK# 重複執行 = 開關切換(toggle)，再按一次就關掉
    #OK# 標記存在 user data，存檔後重開 hip 仍會自動接回
    #OK# 顯示未展開/展開後路徑、幀範圍、檔案存不存在

future features :
    ctrl shift alt function
        現在：ctrl+click = 關閉選取節點的資訊顯示

##############################################################################################################
test env:
    houdini 19.5+
    windows 10
'''

##############################################################################################################
# 【新手導讀 / 這個工具在做什麼】
#
# 情境：網路裡一堆 fetch / filecache / file 節點，光看節點名字根本不知道它讀寫哪個路徑，
#      每次都要點進去看參數，很煩。
#
# 這個工具做的事：
#   1. 把節點的重點資訊(輸出/讀取路徑、幀範圍、檔案在不在)寫進節點的 comment，
#      並打開 comment 顯示旗標，讓資訊直接浮在節點旁邊。
#   2. 【即時】幫這個節點掛一個「參數變更回呼(callback)」。之後你只要改參數，
#      comment 會自己重寫，不用再按一次工具。
#
# 使用方式：
#   - 選取節點 → 執行工具 → 開啟資訊顯示(且即時更新)。
#   - 對「已經開啟」的節點再執行一次 → 關閉(toggle)。
#   - ctrl + click 工具 → 強制關閉選取節點的資訊顯示。
#   - 什麼都不選 → 只做「刷新」：把場景裡所有已標記的節點重新算一次 comment。
#
# 【為什麼要用 callback 才能「即時」】
#   Houdini 的 comment 欄位只吃純文字，不能像參數那樣寫表達式，所以它不會自己更新。
#   唯一能做到即時的方法，就是請 Houdini 在「這個節點的參數被改動時」通知我們，
#   我們收到通知再把 comment 重寫一次 —— 這就是 hou.node.addEventCallback。
#
# 【callback 存不進 hip 檔，所以要有「標記」】
#   callback 只是 Python 記憶體裡的東西，存檔時不會被存進 hip。
#   所以我們額外在節點上寫一個 user data 當標記(user data 會跟著 hip 存檔)，
#   下次開檔時再依標記把 callback 重新掛回去(見 _on_hip_loaded)。
#
# 名詞小抄：
#   - parm(參數)      ：節點上的欄位，例如 filecache 的 "file" 就是它的輸出路徑。
#   - unexpandedString：參數的「原始字串」，$HIP / $F4 都還在。
#   - eval()          ：把變數/表達式算成最終實際值。
#   - callback(回呼)  ：先跟 Houdini 登記「發生某事時請呼叫我這個函式」。
#   - user data       ：掛在節點上的自訂鍵值資料，會跟著 hip 檔一起存檔。
##############################################################################################################

##############################################################################################################
# start
# ---- 匯入需要的模組 ----
import os   # 只用來檢查檔案/資料夾存不存在
import hou  # Houdini 的 Python API，只有在 Houdini 裡面才有這個模組

# ---- 手動設定區(想改行為，主要就是改這裡) ----

# 節點上的標記名稱。有這個 user data 的節點 = 已開啟資訊顯示。
# 開頭用 mijo_ 是為了跟別人的工具區隔，不要跟人撞名。
USER_DATA_KEY = 'mijo_auto_info'

# 是否要順便檢查「檔案/資料夾到底存不存在」。
# 好處：一眼就知道快取算了沒。壞處：路徑在網路磁碟時，這個檢查可能會有點延遲。
# 覺得卡的話就改成 False。
CHECK_FILE_EXISTS = True

# comment 裡「未展開路徑」和「展開後路徑」要不要都顯示。
# 兩者一樣時(例如路徑裡根本沒有 $HIP、$F)只會顯示一行，不會重複。
SHOW_EXPANDED_PATH = True

# start
##############################################################################################################
# functions


# ---- 各種節點的「輸出/讀取路徑」參數對照表 ----
#
# 為什麼要這張表？因為每種節點放路徑的參數名稱都不一樣：
#   ROP geometry 叫 sopoutput、mantra 叫 vm_picture、Redshift 叫 RS_outputFileNamePrefix...
# 所以只能一個一個對。
#
# 比對方式是「節點型別名稱的開頭」(startswith)，不是完全相等。
# 原因：Houdini 的型別名稱常常帶版本號，例如 filecache::2.0、labs::xxx::1.5。
#      用開頭比對，之後 SideFX 出 filecache::3.0 這支腳本也還能用，不用改。
#
# 格式：(型別名稱開頭, 參數名稱, 顯示在 comment 上的標題)
# 順序有意義：由上往下找，第一個對上的就用。
# 想支援新節點？在這裡加一行就好，下面的程式碼完全不用動。
PATH_PARM_RULES = [
    ('fetch',          'source',                  'fetch Path'),
    ('filecache',      'file',                    'cache Path'),
    ('file',           'file',                    'file Path'),
    ('rop_geometry',   'sopoutput',               'SOP Output'),
    ('geometry',       'sopoutput',               'SOP Output'),
    ('rop_alembic',    'filename',                'ABC Output'),
    ('alembic',        'fileName',                'ABC Path'),
    ('ifd',            'vm_picture',              'Mantra Output'),
    ('Redshift_ROP',   'RS_outputFileNamePrefix', 'Redshift Output'),
    ('arnold',         'ar_picture',              'Arnold Output'),
    ('karma',          'picture',                 'Karma Output'),
    ('opengl',         'picture',                 'OpenGL Output'),
    ('usd',            'lopoutput',               'USD Output'),
    ('comp',           'copoutput',               'COP Output'),
    ('object_merge',   'objpath1',                'Merge From'),
]


def find_path_parm(node):
    # 目的：給一個節點，回傳 (參數物件, 標題)；找不到就回傳 (None, None)。
    #
    # 為什麼不用舊版的 str(node.type()) 去比對？
    #   舊寫法是拿「節點型別的文字描述」(長得像 '<hou.NodeType for Driver fetch>')來比字串。
    #   那串文字是給人看的除錯訊息，SideFX 隨時可以改格式，改了這支腳本就整個失效。
    #   type().name() 才是正式的型別名稱(例如 'fetch'、'filecache::2.0')，穩定很多。
    type_name = node.type().name()

    for prefix, parm_name, label in PATH_PARM_RULES:
        if not type_name.startswith(prefix):
            continue  # 型別開頭對不上，換下一條規則
        parm = node.parm(parm_name)
        if parm is None:
            continue  # 型別對上了但沒這個參數(可能是版本差異)，當作沒對上，繼續找
        return parm, label

    return None, None


def get_frame_range_text(node):
    # 目的：如果這個節點有幀範圍設定，回傳像 'frames : 1 - 240' 的字串；沒有就回傳空字串。
    #
    # Houdini 慣例：trange 參數 = 0 代表「只算目前這一幀」，此時 f1/f2 沒意義，不用顯示。
    trange = node.parm('trange')
    if trange is not None and trange.eval() == 0:
        return ''

    f1 = node.parm('f1')
    f2 = node.parm('f2')
    if f1 is None or f2 is None:
        return ''  # 這個節點根本沒有幀範圍參數

    # int() 是為了避免印出 1.0 - 240.0 這種醜醜的小數
    return 'frames : ' + str(int(f1.eval())) + ' - ' + str(int(f2.eval()))


def get_exists_text(path):
    # 目的：檢查路徑到底有沒有東西，回傳一行狀態字串。
    #
    # 這裡收到的 path 是「已展開」的真實路徑。有兩種情況要分開處理：
    #   1. 序列檔(路徑裡有 $F / $T)：展開後只會是「某一幀」的檔名，
    #      去檢查那個單檔意義不大(你可能只是還沒跳到那一幀)，
    #      所以改成檢查「資料夾在不在」比較合理。
    #   2. 單檔：直接檢查檔案本身。
    if not CHECK_FILE_EXISTS or not path:
        return ''

    try:
        # 注意：這裡要用「未展開前有沒有 $F」來判斷，但我們手上只有展開後的字串，
        # 所以改用一個簡單可靠的方式：檢查檔案存在，不存在再退一步檢查資料夾。
        if os.path.isfile(path):
            return 'status : file OK'

        folder = os.path.dirname(path)
        if folder and os.path.isdir(folder):
            # 資料夾在、但這一幀的檔案不在 → 通常代表「算了一部分」或「還沒算到這幀」
            return 'status : dir OK (this frame not found)'

        return 'status : !! NOT FOUND !!'
    except OSError:
        # 網路斷線、權限不足之類的狀況。不要讓一個檢查搞掛整個工具。
        return 'status : ?? (check failed)'


def build_info_text(node):
    # 目的：把一個節點要顯示的所有資訊組成一整段文字(就是最後寫進 comment 的內容)。
    # 回傳空字串 = 這個節點沒有我們認得的資訊，不值得顯示。
    parm, label = find_path_parm(node)
    if parm is None:
        return ''

    raw = parm.unexpandedString()   # 原始字串，$HIP / $F4 都還在 → 給人看比較容易懂
    expanded = parm.eval()          # 展開後的真實路徑 → 用來檢查檔案存不存在

    lines = [label + ' :', raw]

    # 只有在「展開後真的不一樣」時才多印一行，避免同樣的東西看兩次佔空間。
    if SHOW_EXPANDED_PATH and expanded and expanded != raw:
        lines.append('-> ' + expanded)

    frame_text = get_frame_range_text(node)
    if frame_text:
        lines.append(frame_text)

    exists_text = get_exists_text(expanded)
    if exists_text:
        lines.append(exists_text)

    # fetch 節點比較特別：它的 source 指的是「另一個 ROP 節點的路徑」，不是檔案路徑。
    # 光看到 /out/geo1 其實還是不知道它會輸出到哪，所以這裡多跑一步：
    # 把那個目標節點找出來，順便把「它的」輸出路徑也一起顯示。
    if node.type().name().startswith('fetch'):
        target = hou.node(expanded) if expanded else None
        if target is not None:
            target_parm, target_label = find_path_parm(target)
            if target_parm is not None:
                lines.append('')  # 空一行，視覺上把兩段分開
                lines.append(target_label + ' :')
                lines.append(target_parm.unexpandedString())

    return '\n'.join(lines)


def refresh_node(node):
    # 目的：重新計算一個節點的 comment 並寫回去。
    # 這個函式會被兩個地方呼叫：使用者按工具時、以及參數變動的 callback 觸發時。
    text = build_info_text(node)
    if not text:
        return False  # 沒東西可顯示

    node.setComment(text)
    node.setGenericFlag(hou.nodeFlag.DisplayComment, True)  # 打開「在節點旁顯示 comment」
    return True


# functions
##############################################################################################################
# callback 相關(即時更新的核心)


def on_node_changed(**kwargs):
    # 這就是註冊給 Houdini 的回呼函式：只要被監看的節點有參數被改動，Houdini 就會呼叫它。
    #
    # Houdini 是用「關鍵字參數」的方式呼叫，會塞進 node / event_type / parm_tuple 等等。
    # 我們只需要 node，其他用 **kwargs 一併收下忽略掉即可
    # (寫成 **kwargs 也比較安全：以後 SideFX 多塞新參數進來，這裡也不會爆掉)。
    node = kwargs.get('node')
    if node is None:
        return

    # callback 裡發生的例外會被 Houdini 直接丟到 console，很吵，
    # 而且節點被刪掉時本來就可能抓不到 → 這裡整段包起來，安靜失敗就好。
    try:
        refresh_node(node)
    except hou.ObjectWasDeleted:
        pass  # 節點已經被刪了，正常現象，不用理它
    except Exception as e:
        print('mijo auto info : refresh failed : ' + str(e))


def remove_our_callbacks(node):
    # 目的：把「我們自己掛上去的」callback 拆掉，別人掛的不能動。
    #
    # 為什麼不能直接用 removeEventCallback(on_node_changed)？
    #   因為這支腳本是用 reload() 重新載入的。reload 之後，模組裡的 on_node_changed
    #   會變成一個「全新的函式物件」，跟之前掛上去的那個舊物件不是同一個東西，
    #   拿新的去比對根本對不上，舊的就永遠拆不掉、越掛越多。
    # 所以改成比對「函式名稱」字串 —— 名稱在 reload 前後都是一樣的。
    for event_types, callback in node.eventCallbacks():
        if getattr(callback, '__name__', '') == 'on_node_changed':
            node.removeEventCallback(event_types, callback)


def watch_node(node):
    # 目的：開始監看一個節點(掛上 callback + 蓋上標記)。
    remove_our_callbacks(node)  # 先拆舊的，避免重複執行時同一個節點被掛好幾次

    # ParmTupleChanged = 「有參數被改動」。這就是即時更新的觸發來源。
    node.addEventCallback((hou.nodeEventType.ParmTupleChanged,), on_node_changed)

    # 蓋標記：user data 會跟著 hip 存檔，下次開檔才知道要把 callback 掛回哪些節點。
    # 值本身不重要，重點是「這個 key 存不存在」，所以隨便給個 '1'。
    node.setUserData(USER_DATA_KEY, '1')

    refresh_node(node)  # 立刻先算一次，不用等使用者去改參數


def unwatch_node(node):
    # 目的：停止監看(拆 callback + 清標記 + 清掉 comment)。
    remove_our_callbacks(node)

    # must_exist=False：就算本來就沒有這個 user data 也不要報錯。
    node.destroyUserData(USER_DATA_KEY, must_exist=False)

    node.setComment('')
    node.setGenericFlag(hou.nodeFlag.DisplayComment, False)


def is_watched(node):
    # 目的：這個節點目前是不是「已開啟」狀態？靠 user data 標記判斷。
    return node.userData(USER_DATA_KEY) is not None


def get_all_watched_nodes():
    # 目的：把整個場景裡「有蓋標記」的節點全部找出來。
    #
    # 用途有二：使用者沒選任何節點時的「全部刷新」、以及開檔後重新掛 callback。
    # 作法：從根節點 / 開始，遞迴走訪所有子節點(allSubChildren 會一路挖到最底層)。
    root = hou.node('/')
    return [n for n in root.allSubChildren() if is_watched(n)]


def on_hip_loaded(event_type):
    # 目的：hip 檔載入後，把 callback 重新掛回所有有標記的節點。
    #
    # 前面說過：callback 只活在記憶體，存檔不會被存進 hip；
    # 但 user data 標記會。所以開檔後就靠標記把監看狀態「復原」回來。
    if event_type != hou.hipFileEventType.AfterLoad:
        return  # 其他事件(存檔前、清空場景...)不用理

    for node in get_all_watched_nodes():
        try:
            remove_our_callbacks(node)
            node.addEventCallback((hou.nodeEventType.ParmTupleChanged,), on_node_changed)
        except hou.OperationFailed:
            pass


def install_hip_callback():
    # 目的：登記「hip 檔載入完成時請通知我」。
    #
    # 同樣的 reload 問題：不能用函式物件比對，要用名稱比對來拆舊的，
    # 否則每 reload 一次就多掛一個，開檔時會重複跑好幾遍。
    for cb in hou.hipFile.eventCallbacks():
        if getattr(cb, '__name__', '') == 'on_hip_loaded':
            hou.hipFile.removeEventCallback(cb)

    hou.hipFile.addEventCallback(on_hip_loaded)


# callback 相關
##############################################################################################################
# process


def main():
    print('-----------------------------------')

    install_hip_callback()  # 每次執行都確保「開檔自動接回」這件事有登記好

    # 讀取 shelf 傳過來的按鍵狀態(ctrl / shift / alt 有沒有被按著)。
    # 這是由 mijo_tools.shelf 裡的 shelf script 幫我們放進 hou.session 的，
    # 因為 shelf 的 kwargs 只存在於 shelf script 那層，import 進來的模組拿不到。
    # 用 getattr 給預設值 {}：萬一是從別的地方直接跑這支腳本，也不會因為沒有 kwargs 就爆掉。
    shelf_kwargs = getattr(hou.session, 'mijo_shelf_kwargs', {})
    force_off = shelf_kwargs.get('ctrlclick', False)

    nodes = hou.selectedNodes()

    # 什麼都沒選 → 解讀成「幫我把所有已開啟的節點刷新一下」。
    # (正常情況下 callback 就會自動更新了，這條路主要是備援：
    #  例如檔案在別的地方被算好了，但參數沒動過，callback 自然不會被觸發。)
    if not nodes:
        watched = get_all_watched_nodes()
        for n in watched:
            refresh_node(n)
        print('沒有選取節點 → 已刷新 ' + str(len(watched)) + ' 個節點的資訊')
        print('-----------------------------------')
        return

    on_count = 0
    off_count = 0
    skip_count = 0

    for n in nodes:
        # ctrl+click，或這個節點本來就是開的 → 關掉它(這就是 toggle)
        if force_off or is_watched(n):
            unwatch_node(n)
            off_count += 1
            continue

        # 認不出來的節點型別就跳過，不要硬掛 callback 上去白費工。
        # (想支援它？去上面的 PATH_PARM_RULES 加一行。)
        if not build_info_text(n):
            print('    skip : "' + n.name() + '" (' + n.type().name() +
                  ') 沒有支援的路徑參數')
            skip_count += 1
            continue

        watch_node(n)
        on_count += 1

    print('資訊顯示 : 開啟 ' + str(on_count) + ' / 關閉 ' + str(off_count) +
          ' / 略過 ' + str(skip_count))
    print('已開啟的節點會在參數變更時自動更新 comment')
    print('-----------------------------------')


# 這支腳本被 shelf 工具載入(reload)後會直接執行 main()，所以最後直接呼叫它。
main()

# process
##############################################################################################################
