# solaris render QC
# by mijo

'''
roadmap:
    出圖前一鍵體檢：camera / 解析度 / 輸出路徑 / 幀範圍，避免農場跑一半才發現設錯

features 20260717 :
    #OK# 支援 Karma(LOP) / USD Render ROP / Render Settings LOP / Redshift / Arnold
    #OK# camera 檢查：有沒有設、路徑格式對不對、(深度模式)stage 上到底存不存在
    #OK# 輸出路徑檢查：空值 / 序列缺 $F / 副檔名 / 本機硬碟 / 根目錄白名單 / 資料夾在不在
    #OK# 解析度檢查：0 或負數、奇數(部分編碼器會爆)
    #OK# 幀範圍檢查：f1 > f2、frame step 不是 1
    #OK# 預設「淺層檢查」不 cook stage，不吃效能；ctrl+click 才做深度檢查
    #OK# 沒選節點 = 掃描整個 /stage 底下所有 render 節點

future features :
    ctrl shift alt function
        現在：ctrl+click = 深度檢查(會 cook stage，比較慢但最準)

##############################################################################################################
test env:
    houdini 19.5+ (Solaris)
    windows 10
'''

##############################################################################################################
# 【新手導讀 / 這個工具在做什麼】
#
# 情境：Solaris 裡設好 Karma / Redshift / Arnold，按下 render 丟去農場，
#      跑了兩小時才發現 camera 根本沒指定、或輸出路徑少了 $F4 導致每一幀互相覆蓋、
#      或路徑寫在自己電腦的 C:\ 農場機器根本讀不到。這些都是「早該一眼看出來」的低級錯誤。
#
# 這個工具做的事：
#   出圖前按一下，把場景裡的 render 節點抓出來，逐項檢查最基礎的 QC 項目，
#   然後在 console 印出一份報告，告訴你哪個節點的哪個參數有問題。
#
# 使用方式：
#   - 什麼都不選 → 掃描 /stage(和 /out)底下所有認得的 render 節點。
#   - 選取節點   → 只檢查選取的那些。
#   - ctrl+click → 深度檢查(會去 cook stage，真的去確認 camera prim 存不存在)。
#
# 【為什麼要分「淺層」和「深度」】
#   要確認「camera 這個 prim 到底在不在 stage 上」，唯一的方法是把 LOP 網路算出來(cook)。
#   場景大的時候 cook 可能要等好幾秒甚至更久 —— 這違背了「快速 check」的初衷。
#   所以預設只做「參數層級」的檢查(讀參數字串，幾乎不花時間)，
#   真的想確認 prim 存在時再 ctrl+click 做深度檢查。
#
# 【檢查結果的三種等級】
#   ERROR : 幾乎確定出不了圖，或出來的東西是壞的 → 一定要修。
#   WARN  : 不一定是錯，但很可疑，請你自己確認一下。
#   OK    : 這項通過。
#
# 名詞小抄：
#   - LOP        ：Solaris 的節點(在 /stage 裡面那些)。
#   - stage      ：LOP 網路算出來的結果，就是一棵 USD 場景樹。
#   - prim       ：USD 場景樹上的一個節點,例如 /cameras/camMain。
#   - $F4        ：Houdini 的幀號變數,展開後會變成 0001、0002...,序列輸出一定要有。
#   - unexpandedString：參數的「原始字串」,$HIP / $F4 都還在。
##############################################################################################################

##############################################################################################################
# start
# ---- 匯入需要的模組 ----
import os   # 只用來檢查資料夾存不存在
import hou  # Houdini 的 Python API，只有在 Houdini 裡面才有這個模組

# ---- 手動設定區(想改行為，主要就是改這裡) ----

# 輸出路徑「必須」放在這些根目錄底下(不分大小寫)。
# 這是給團隊定規則用的：例如公司規定成果一律寫到專案伺服器，不准寫在桌面。
# 留空的 list = 不檢查這一項(個人使用或還沒定規則時就留空)。
# 範例：ALLOWED_OUTPUT_ROOTS = ['P:/', 'Z:/projects/']
ALLOWED_OUTPUT_ROOTS = []

# 輸出路徑不該出現的磁碟機。
# 為什麼要有這個：農場的機器不是你的機器，你的 C: 或 D: 上的資料夾它讀不到也寫不進去，
# 一送出去就是整批 job 失敗。
LOCAL_DRIVERS = ['C:', 'D:']

# 允許的輸出副檔名。不在這裡面的會出 WARN(不是 ERROR，因為你可能真的有特殊需求)。
ALLOWED_IMAGE_EXTS = ['.exr', '.png', '.jpg', '.jpeg', '.tif', '.tiff']

# 要不要檢查「輸出資料夾存不存在」。
# 好處：一眼看出路徑打錯字。壞處：路徑在網路磁碟時這個檢查會有點延遲。
# 覺得卡的話就改成 False。
CHECK_OUTPUT_DIR = True

# 解析度低於這個值就當作可疑(通常是測試完忘了調回來就送出去了)。
MIN_RESOLUTION = 64

# 要不要順便把檢查結果寫進節點的 comment。
# 開啟的話，有問題的節點會直接在網路圖上標紅字，不用回頭看 console。
WRITE_TO_COMMENT = True

# start
##############################################################################################################
# functions


# ---- 各種 render 節點的「參數對照表」----
#
# 為什麼要這張表？因為每家 renderer 放同一種東西的參數名稱都不一樣：
#   Karma 的相機叫 camera、Redshift 叫 RS_renderCamera、USD Render ROP 叫 override_camera...
# 所以只能一個一個對。
#
# 比對方式是「節點型別名稱的開頭」(startswith)，不是完全相等。
# 原因：Houdini 的型別名稱常常帶版本號，例如 karma::3.0、usdrender_rop::2.0。
#      用開頭比對，之後 SideFX 出新版本這支腳本也還能用，不用改。
#
# 每個欄位都是「候選參數名稱的清單」，由左往右找，找到第一個存在的就用。
# 為什麼要用清單而不是單一名稱？因為同一個節點不同版本可能改過參數名，
# 多列幾個候選比較耐命，猜錯一個也不會整個工具失效。
#
# 想支援新的 renderer？在這裡加一筆就好，下面的檢查邏輯完全不用動。
RENDER_NODE_RULES = [
    {
        'prefix':     'karma',
        'label':      'Karma (LOP)',
        'camera':     ['camera'],
        'output':     ['picture'],
        'res_x':      ['resolutionx', 'res_overridex'],
        'res_y':      ['resolutiony', 'res_overridey'],
    },
    {
        'prefix':     'usdrender_rop',
        'label':      'USD Render ROP',
        'camera':     ['override_camera', 'camera'],
        'output':     ['outputimage', 'picture'],
        'res_x':      ['override_resolutionx', 'resolutionx'],
        'res_y':      ['override_resolutiony', 'resolutiony'],
    },
    {
        'prefix':     'usdrender',
        'label':      'USD Render',
        'camera':     ['override_camera', 'camera'],
        'output':     ['outputimage', 'picture'],
        'res_x':      ['override_resolutionx', 'resolutionx'],
        'res_y':      ['override_resolutiony', 'resolutiony'],
    },
    {
        'prefix':     'rendersettings',
        'label':      'Render Settings (LOP)',
        'camera':     ['camera'],
        'output':     [],   # rendersettings 本身不出圖，輸出路徑在 renderproduct 上
        'res_x':      ['resolutionx'],
        'res_y':      ['resolutiony'],
    },
    {
        'prefix':     'renderproduct',
        'label':      'Render Product (LOP)',
        'camera':     [],
        'output':     ['productname'],
        'res_x':      [],
        'res_y':      [],
    },
    {
        'prefix':     'Redshift_ROP',
        'label':      'Redshift',
        'camera':     ['RS_renderCamera'],
        'output':     ['RS_outputFileNamePrefix'],
        'res_x':      ['RS_overrideCameraResX'],
        'res_y':      ['RS_overrideCameraResY'],
    },
    {
        'prefix':     'arnold',
        'label':      'Arnold',
        'camera':     ['camera', 'ar_camera'],
        'output':     ['ar_picture', 'picture'],
        'res_x':      ['override_camerares', 'ar_resolutionx'],
        'res_y':      ['ar_resolutiony'],
    },
]


def find_rule(node):
    # 目的：給一個節點，回傳它對應的規則(dict)；認不出來就回傳 None。
    #
    # 用 type().name() 而不是 str(node.type())：
    #   後者是給人看的除錯字串('<hou.NodeType for Lop karma>')，SideFX 隨時可以改格式。
    #   type().name() 才是正式的型別名稱(例如 'karma::3.0')，穩定很多。
    type_name = node.type().name()
    for rule in RENDER_NODE_RULES:
        if type_name.startswith(rule['prefix']):
            return rule
    return None


def get_parm(node, names):
    # 目的：從候選名稱清單裡找出第一個「這個節點真的有」的參數。
    # 找不到就回傳 None —— 這通常代表這版節點沒這個參數，不是錯誤，交給呼叫端決定怎麼處理。
    for name in names:
        parm = node.parm(name)
        if parm is not None:
            return parm
    return None


def is_disabled(parm):
    # 目的：這個參數現在是不是「被鎖住/沒作用」的狀態？
    #
    # 為什麼要判斷：很多 override 參數前面有個開關(toggle)，開關沒打開時參數是灰的。
    # 灰掉的參數就算內容是空的也不是錯誤 —— 使用者本來就沒打算用它。
    # 對這種參數報 ERROR 只會製造假警報，久了大家就不看報告了。
    try:
        return parm.isDisabled()
    except AttributeError:
        return False  # 舊版 Houdini 沒這個 API，當作沒鎖住，繼續檢查


# functions
##############################################################################################################
# 各項檢查(每個函式回傳一串 (等級, 訊息))


def check_camera(node, rule, deep):
    # 目的：檢查相機設定。這是最容易忘記、後果又最嚴重的一項
    #      (沒相機 = 整批算出來是黑的或直接失敗)。
    parm = get_parm(node, rule['camera'])
    if parm is None:
        return []  # 這個節點型別沒有相機參數(例如 renderproduct)，不用檢查

    if is_disabled(parm):
        return [('OK', 'camera : 未啟用 override(使用上游設定)')]

    raw = parm.unexpandedString().strip()
    if not raw:
        return [('ERROR', 'camera : 沒有指定相機')]

    path = parm.eval().strip()

    # USD 的 prim path 一定是絕對路徑，以 / 開頭。
    # 不是的話八成是打錯字，或誤填了 Houdini 的節點路徑(那是另一個世界的東西)。
    if not path.startswith('/'):
        return [('ERROR', 'camera : "' + raw + '" 不是合法的 USD prim path(要以 / 開頭)')]

    results = [('OK', 'camera : ' + path)]

    # 以下是深度檢查：真的去 stage 上把這個 prim 找出來。
    # 淺層模式直接跳過，因為 stage() 會觸發 cook，場景大時會卡住。
    if not deep:
        return results

    stage = get_stage(node)
    if stage is None:
        results.append(('WARN', 'camera : 無法取得 stage，跳過存在性檢查'))
        return results

    prim = stage.GetPrimAtPath(path)
    if not prim or not prim.IsValid():
        results.append(('ERROR', 'camera : stage 上找不到 "' + path + '"'))
        return results

    # 找到了，但它是不是「相機」？
    # 指到一個 Xform 或 Mesh 也是常見錯誤(通常是選錯了層級，選到相機的爸爸)。
    if prim.GetTypeName() != 'Camera':
        results.append(('ERROR', 'camera : "' + path + '" 不是 Camera，而是 ' +
                        str(prim.GetTypeName())))

    return results


def check_output(node, rule, deep):
    # 目的：檢查輸出路徑。第二容易出事的地方，而且錯了通常是整批重算。
    parm = get_parm(node, rule['output'])
    if parm is None:
        return []

    if is_disabled(parm):
        return [('OK', 'output : 未啟用 override')]

    raw = parm.unexpandedString().strip()
    if not raw:
        return [('ERROR', 'output : 輸出路徑是空的')]

    results = [('OK', 'output : ' + raw)]
    expanded = parm.eval().strip()

    # ---- 序列檢查 ----
    # 只算一幀($F 沒意義)就跳過；要算序列卻沒有 $F = 每一幀都寫到同一個檔名，
    # 前面算的會被後面蓋掉，最後只剩最後一幀。這是最經典的災難。
    if is_frame_sequence(node) and '$F' not in raw and '$T' not in raw:
        results.append(('ERROR', 'output : 算序列但路徑沒有 $F，每幀會互相覆蓋'))

    # ---- 副檔名檢查 ----
    ext = os.path.splitext(expanded)[1].lower()
    if not ext:
        results.append(('ERROR', 'output : 路徑沒有副檔名'))
    elif ALLOWED_IMAGE_EXTS and ext not in ALLOWED_IMAGE_EXTS:
        results.append(('WARN', 'output : 副檔名 "' + ext + '" 不在允許清單內'))

    # ---- 本機硬碟檢查 ----
    # 用展開後的路徑判斷：$HIP 可能本身就展開成 C:\...，看原始字串是看不出來的。
    drive = expanded[:2].upper()
    if drive in [d.upper() for d in LOCAL_DRIVERS]:
        results.append(('ERROR', 'output : 寫在本機硬碟 ' + drive + '，農場機器讀不到'))

    # ---- 根目錄白名單檢查 ----
    if ALLOWED_OUTPUT_ROOTS:
        norm = expanded.replace('\\', '/').lower()
        hit = False
        for root in ALLOWED_OUTPUT_ROOTS:
            if norm.startswith(root.replace('\\', '/').lower()):
                hit = True
                break
        if not hit:
            results.append(('ERROR', 'output : 不在允許的根目錄底下 ' +
                            str(ALLOWED_OUTPUT_ROOTS)))

    # ---- 資料夾檢查 ----
    # 注意：只檢查資料夾，不檢查檔案。檔案本來就還沒算出來，檢查它沒意義。
    if CHECK_OUTPUT_DIR:
        folder = os.path.dirname(expanded)
        if folder:
            try:
                if not os.path.isdir(folder):
                    # 這是 WARN 不是 ERROR：多數 renderer 會自己建資料夾，
                    # 所以資料夾不存在通常沒事 —— 但也可能是你路徑打錯字。請自己看一眼。
                    results.append(('WARN', 'output : 資料夾不存在 "' + folder + '"'))
            except OSError:
                # 網路斷線、權限不足之類的。不要讓一個檢查搞掛整個工具。
                results.append(('WARN', 'output : 資料夾檢查失敗(網路或權限?)'))

    return results


def check_resolution(node, rule, deep):
    # 目的：檢查解析度。最常見的狀況是「測試時調成 320，出圖前忘了調回來」。
    parm_x = get_parm(node, rule['res_x'])
    parm_y = get_parm(node, rule['res_y'])
    if parm_x is None or parm_y is None:
        return []

    if is_disabled(parm_x):
        return [('OK', 'resolution : 未啟用 override(使用相機設定)')]

    res_x = int(parm_x.eval())
    res_y = int(parm_y.eval())

    if res_x <= 0 or res_y <= 0:
        return [('ERROR', 'resolution : ' + str(res_x) + ' x ' + str(res_y) + ' 不合法')]

    results = [('OK', 'resolution : ' + str(res_x) + ' x ' + str(res_y))]

    if res_x < MIN_RESOLUTION or res_y < MIN_RESOLUTION:
        results.append(('WARN', 'resolution : 太小了，是不是測試完忘了改回來?'))

    # 奇數解析度：h264/h265 這類編碼器要求偶數，後製轉檔時會失敗或被硬裁一個 pixel。
    if res_x % 2 or res_y % 2:
        results.append(('WARN', 'resolution : 有奇數邊長，之後轉 mp4 可能會出問題'))

    return results


def check_frame_range(node, rule, deep):
    # 目的：檢查幀範圍。錯了不會失敗，但會安靜地算出錯的東西 —— 這種最可怕。
    trange = node.parm('trange')
    if trange is None:
        return []

    # Houdini 慣例：trange = 0 代表「只算目前這一幀」，此時 f1/f2 沒意義。
    if trange.eval() == 0:
        return [('WARN', 'frames : 設定成只算目前這一幀(Render Current Frame)')]

    f1 = node.parm('f1')
    f2 = node.parm('f2')
    if f1 is None or f2 is None:
        return []

    start = int(f1.eval())
    end = int(f2.eval())

    if start > end:
        return [('ERROR', 'frames : 起始幀 ' + str(start) + ' 大於結束幀 ' + str(end))]

    results = [('OK', 'frames : ' + str(start) + ' - ' + str(end))]

    # frame step 不是 1 = 跳幀算。有時是故意的(算 preview)，但更常是忘了改回來。
    f3 = node.parm('f3')
    if f3 is not None and f3.eval() != 1:
        results.append(('WARN', 'frames : step = ' + str(f3.eval()) + '，不是逐幀算'))

    return results


# 所有檢查項目的清單。想加新檢查？寫一個同樣格式的函式，加進這個 list 就好。
# 格式：函式吃 (node, rule, deep)，回傳 [(等級, 訊息), ...]。
ALL_CHECKS = [
    check_camera,
    check_output,
    check_resolution,
    check_frame_range,
]


# 各項檢查
##############################################################################################################
# 工具函式


def is_frame_sequence(node):
    # 目的：這個節點是不是要算「一段序列」(而不是單張)？
    # 用途：只有算序列時，路徑少了 $F 才算是錯誤。
    trange = node.parm('trange')
    if trange is None:
        return True  # 沒有 trange 參數就保守假設是序列，寧可多提醒
    return trange.eval() != 0


def get_stage(node):
    # 目的：拿到這個節點算出來的 USD stage。拿不到就回傳 None。
    #
    # 警告：這個函式會觸發 cook，可能很慢 —— 所以只在深度模式下呼叫。
    # 用 try 包起來的原因：節點可能根本不是 LOP(例如 /out 底下的 ROP)，
    # 或是 LOP 網路本身有錯 cook 不出來。這兩種情況都不該讓整個工具掛掉。
    try:
        return node.stage()
    except (AttributeError, hou.OperationFailed, hou.LoadWarning):
        return None


def find_render_nodes():
    # 目的：沒選節點時，自動把場景裡所有認得的 render 節點找出來。
    #
    # 只掃 /stage 和 /out：render 節點理論上只會在這兩個地方，
    # 從 / 開始 allSubChildren() 會把整個場景(可能上萬個節點)走一遍，太浪費。
    found = []
    for root_path in ['/stage', '/out']:
        root = hou.node(root_path)
        if root is None:
            continue
        for n in root.allSubChildren():
            if find_rule(n) is not None:
                found.append(n)
    return found


def check_node(node, deep):
    # 目的：把一個節點的所有檢查跑完，回傳 [(等級, 訊息), ...]。
    rule = find_rule(node)
    if rule is None:
        return None  # 認不出來的節點型別，回 None 讓呼叫端知道要「略過」而不是「通過」

    results = []
    for check in ALL_CHECKS:
        try:
            results.extend(check(node, rule, deep))
        except Exception as e:
            # 單項檢查爆掉不該拖垮其他項目 —— 報告裡照實寫出來就好。
            # (最常見原因：某版節點的參數型別跟預期不同。)
            results.append(('WARN', check.__name__ + ' 檢查失敗 : ' + str(e)))

    return results


def worst_level(results):
    # 目的：這個節點整體算「過」還是「不過」？取最嚴重的那一項。
    levels = [lv for lv, _ in results]
    if 'ERROR' in levels:
        return 'ERROR'
    if 'WARN' in levels:
        return 'WARN'
    return 'OK'


def write_comment(node, results, level):
    # 目的：把有問題的項目寫進節點 comment，讓你在網路圖上直接看到，不用回頭翻 console。
    if level == 'OK':
        # 通過的節點就把 comment 清掉(可能是上一次檢查留下來的舊訊息)。
        # 這裡不能無條件清空 —— 別人手寫的 comment 不是我們的東西，不能亂刪。
        # 所以只清掉「開頭是我們標記」的那種。
        if node.comment().startswith('[QC]'):
            node.setComment('')
            node.setGenericFlag(hou.nodeFlag.DisplayComment, False)
        return

    lines = ['[QC] ' + level]
    for lv, msg in results:
        if lv != 'OK':
            lines.append(lv + ' : ' + msg)

    node.setComment('\n'.join(lines))
    node.setGenericFlag(hou.nodeFlag.DisplayComment, True)


# 工具函式
##############################################################################################################
# process


def main():
    print('-----------------------------------')
    print('Solaris Render QC')

    # 讀取 shelf 傳過來的按鍵狀態(ctrl / shift / alt 有沒有被按著)。
    # 這是由 mijo_tools.shelf 裡的 shelf script 幫我們放進 hou.session 的，
    # 因為 shelf 的 kwargs 只存在於 shelf script 那層，import 進來的模組拿不到。
    # 用 getattr 給預設值 {}：萬一是從別的地方直接跑這支腳本，也不會因為沒有 kwargs 就爆掉。
    shelf_kwargs = getattr(hou.session, 'mijo_shelf_kwargs', {})
    deep = shelf_kwargs.get('ctrlclick', False)

    nodes = hou.selectedNodes()
    if not nodes:
        nodes = find_render_nodes()
        print('沒有選取節點 → 掃描 /stage 與 /out')

    if deep:
        print('模式 : 深度檢查(會 cook stage，比較慢)')
    else:
        print('模式 : 快速檢查(不 cook stage / ctrl+click 可做深度檢查)')

    print('')

    error_count = 0
    warn_count = 0
    pass_count = 0
    skip_count = 0

    for n in nodes:
        results = check_node(n, deep)
        if results is None:
            skip_count += 1
            continue

        level = worst_level(results)
        if level == 'ERROR':
            error_count += 1
        elif level == 'WARN':
            warn_count += 1
        else:
            pass_count += 1

        print('[' + level + '] ' + n.path() + '  (' + find_rule(n)['label'] + ')')
        for lv, msg in results:
            # OK 的項目只在「這個節點整體通過」時才印。
            # 否則報告會被一堆 OK 洗版，真正的問題反而看不到。
            if lv == 'OK' and level != 'OK':
                continue
            print('    ' + lv + ' : ' + msg)
        print('')

        if WRITE_TO_COMMENT:
            write_comment(n, results, level)

    print('-----------------------------------')
    print('檢查完成 : ' + str(error_count) + ' 個 ERROR / ' +
          str(warn_count) + ' 個 WARN / ' +
          str(pass_count) + ' 個通過 / ' +
          str(skip_count) + ' 個略過(不是 render 節點)')

    if error_count:
        print('!! 有 ERROR，出圖前請先修掉 !!')

    print('-----------------------------------')


# 這支腳本被 shelf 工具載入(reload)後會直接執行 main()，所以最後直接呼叫它。
main()

# process
##############################################################################################################
