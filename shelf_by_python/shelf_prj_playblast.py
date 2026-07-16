# project based playblast
# by mijo

'''
roadmap:
    一鍵 playblast：用「專案設定」自動決定解析度/幀率/輸出路徑，出圖 + 轉檔 + 開檔全自動

features 20260717 :
    #OK# 用環境變數 MIJO_PROJECT 判斷現在是哪個專案
    #OK# 用環境變數 MIJO_PROJECT_CONFIG 讀 JSON 設定檔
    #OK# 三層設定合併：腳本內建預設 <- config 的 default <- config 的 projects[專案名]
    #OK# 沒有 config / 沒有專案 / config 壞掉 → 一律退回內建預設，工具照樣能跑
    #OK# flipbook 出序列 → ffmpeg 轉 mp4/mov → 自動刪暫存序列 → 自動開檔
    #OK# 檔名 token：{project} {hip} {camera} {user} {date} {version}
    #OK# {version} 自動掃描資料夾遞增(v001 → v002)
    #OK# 燒字幕(burn-in)：專案/檔名/相機/幀號，失敗會自動退回不燒字重轉
    #OK# ctrl+click = 出圖前跳確認視窗可微調  shift+click = 保留暫存序列不刪

future features :
    ctrl shift alt function
        現在：ctrl+click = 確認視窗   shift+click = 保留序列
    opengl ROP backend
        現在只有 flipbook(所見即所得,但需要有 Scene Viewer 開著)
        之後可加 opengl ROP,不需要 viewport,適合批次/農場
    config 支援 shot 層級
        現在只到 project 層級,之後可加 projects[X].shots[Y]
    出完自動上傳 / 通知

##############################################################################################################
test env:
    houdini 19.5+
    windows 10
'''

##############################################################################################################
# 【新手導讀 / 這個工具在做什麼】
#
# 情境：想快速出一段預覽影片給人看，現在的流程是 —— 開 flipbook 視窗、手動填解析度、
#      手動填幀範圍、手動選輸出資料夾、出完一堆 jpg 序列、再開另一個軟體轉成 mp4、
#      再自己想檔名、再自己記得這次是 v3 還是 v4。每次都重來一遍，很煩而且很容易填錯。
#
# 這個工具做的事：
#   按一下 → 自動出圖 → 自動轉成 mp4 → 自動命名(含版本號) → 自動開起來看。
#   「解析度多少、幀率多少、檔案放哪」不是你每次填，而是「這個專案本來就規定好」的，
#   工具去查專案設定檔拿。換專案 = 換一個環境變數,設定自動跟著換。
#
# 【設定是怎麼被決定的 —— 三層覆蓋】
#   第 1 層：這支腳本裡的 BUILTIN_DEFAULT(往下看)。什麼都沒設定時用這層 → 這就是「簡單版」。
#   第 2 層：JSON 設定檔裡的 "default"。整間公司/所有專案的共同預設。
#   第 3 層：JSON 設定檔裡的 "projects" -> 你目前的專案。專案自己的特別規定。
#   後面的蓋前面的，只蓋「有寫到的那幾項」。
#   例如專案只寫了 resolution,那 fps 就還是沿用第 2 層(或第 1 層)的值,不用整份重抄。
#
#   → 好處：config 檔不見了、專案名沒設、JSON 打錯字,工具都還是能跑(退回內建預設),
#     不會因為設定檔有問題就整個用不了。
#
# 【第一次用要設兩個環境變數】
#   - MIJO_PROJECT        = 目前專案代號,例如 SHORT_FILM_A
#                           (要跟 JSON 裡 "projects" 底下的 key 對得上)
#   - MIJO_PROJECT_CONFIG = 專案設定 JSON 的路徑,例如 P:/config/mijo_project_config.json
#   兩個都沒設 → 用內建預設,一樣可以出圖,只是解析度/路徑是通用的那組。
#
#   設定方式(擇一)：
#     方式1) Windows 系統環境變數
#     方式2) Houdini 的 houdini.env 加一行： MIJO_PROJECT = "SHORT_FILM_A"
#   這裡用 hou.getenv 讀,上面兩種設法都抓得到。
#
# 【JSON 設定檔長什麼樣】
#   範例在 config/project_config.example.json,複製一份改成自己的即可。
#   也支援「極簡寫法」：整個 JSON 直接就是設定本身(沒有 default/projects 兩層),
#   適合一個專案一個 config 檔的情況。
#
# 使用方式：
#   - 直接 click   → 用專案設定直接出圖,全自動。
#   - ctrl+click   → 出圖前跳一個視窗,讓你臨時改幀範圍/解析度/版本(改完這次有效,不寫回設定檔)。
#   - shift+click  → 保留中間產生的 jpg 序列不刪(想自己拿去做別的事時用)。
#
# 名詞小抄：
#   - flipbook  ：Houdini 的視窗錄影功能,把 viewport 看到的畫面一幀一幀存成圖檔。
#   - ffmpeg    ：業界標準的轉檔工具,這裡拿來把 jpg 序列壓成 mp4。
#   - burn-in   ：燒在畫面上的文字資訊(專案名、幀號...),方便別人看片時對照。
#   - token     ：檔名模板裡的 {xxx} 佔位符,實際輸出時會被換成真的值。
#   - $F4       ：Houdini 的幀號變數,展開後變成 0001、0002...,出序列一定要有。
##############################################################################################################

##############################################################################################################
# start
# ---- 匯入需要的模組 ----
import os            # 路徑、建資料夾、開檔案
import re            # 正規表達式,用來從既有檔名裡找出版本號
import glob          # 用萬用字元(*)列出符合的檔案,掃版本號用
import json          # 讀 JSON 設定檔
import shutil        # shutil.which:在系統 PATH 裡找 ffmpeg   shutil.rmtree:刪暫存資料夾
import getpass       # 取得目前登入的使用者名稱(檔名 token {user} 用)
import datetime      # 取得今天日期(檔名 token {date} 用)
import subprocess    # 啟動外部程式(ffmpeg)
import hou           # Houdini 的 Python API,只有在 Houdini 裡面才有這個模組

# ---- 手動設定區(想改行為,主要就是改這裡) ----

# 環境變數的「名字」。如果你們公司已經有自己的一套命名(例如 SHOW、PROJECT_ROOT),
# 直接把這兩行的字串換掉就好,不用動下面的程式。
ENV_PROJECT = 'MIJO_PROJECT'                # 值 = 專案代號,例如 SHORT_FILM_A
ENV_PROJECT_CONFIG = 'MIJO_PROJECT_CONFIG'  # 值 = JSON 設定檔的完整路徑
ENV_FFMPEG = 'MIJO_FFMPEG'                  # 值 = ffmpeg.exe 的完整路徑(通常不用設,會自動找)

# 【第 1 層設定：內建預設】
# 這就是使用者說的「簡單版」：沒有 config 檔、沒有專案時,就用這一組。
# 也是「保底」：config 裡沒寫到的項目,一律用這裡的值,所以下面每一項都必須有值。
BUILTIN_DEFAULT = {
    # ---- 畫面 ----
    'resolution': [1920, 1080],      # 輸出解析度 [寬, 高]
    'resolution_scale': 1.0,         # 再乘一個倍率。想出半解析度預覽就填 0.5,算很快
    'use_camera_resolution': False,  # True = 忽略上面的 resolution,改用目前 viewport 相機自己的 resx/resy
    'pixel_aspect': 1.0,             # 像素長寬比。一般都是 1.0;做變形寬螢幕(anamorphic)才會不是 1

    # ---- 時間 ----
    'fps': 25,                       # 影片幀率
    'frame_range': 'playbar',        # 'playbar' = 用播放列的範圍  或直接寫 [1001, 1100] 指定範圍
    'frame_step': 1,                 # 每幾幀出一張。填 2 = 隔幀出,速度快一倍但會頓

    # ---- 輸出 ----
    'output_dir': '$HIP/playblast',  # 影片要放哪。可以用 $HIP、$JOB 這種 Houdini 變數
    'output_name': '{hip}_{camera}_{version}',  # 檔名模板,可用的 token 見下方 build_tokens()
    'format': 'mp4',                 # 'mp4'(h264,檔案小,通用) 或 'mov'(ProRes,畫質好,檔案大)
    'quality': 20,                   # 只對 mp4 有效。ffmpeg 的 crf 值:數字越小畫質越好檔案越大(18~23 是常用區間)

    # ---- 出圖細節 ----
    'frame_format': 'jpg',           # 中間暫存序列的格式。jpg 最快;想要無損可填 'png'
    'beauty_pass_only': True,        # True = 不畫格線/操作把手那些輔助圖示,只留畫面本身
    'crop_out_view_mask': True,      # True = 直接裁掉相機遮罩外的黑邊,出來就是乾淨的畫面比例

    # ---- 附加功能 ----
    'burn_in': True,                 # True = 在畫面上燒專案名/檔名/相機/幀號
    'burn_in_font': 'C:/Windows/Fonts/consola.ttf',  # 燒字用的字型檔。換字型改這裡
    'open_after': True,              # True = 轉檔完自動用系統預設播放器打開
    'ffmpeg': '',                    # ffmpeg.exe 路徑。留空 = 自動找(見 find_ffmpeg)
}

# start
##############################################################################################################
# functions


def get_shelf_kwargs():
    # 目的：拿到 shelf 按鈕被按下時的按鍵狀態(有沒有同時按 ctrl/shift/alt)。
    #
    # 為什麼要這樣繞：kwargs 這個變數只存在於 shelf 按鈕自己的 script 那一層,
    # 我們這支被 import 進來的模組是拿不到的。所以 shelf 那邊會先把它塞進
    # hou.session(Houdini 的全域暫存空間),我們再從那裡撈出來。
    # 撈不到就回空的 dict,代表「沒有按任何修飾鍵」,工具照跑。
    return getattr(hou.session, 'mijo_shelf_kwargs', {}) or {}


def expand(path):
    # 把 Houdini 變數($HIP、$JOB、$F...)展開成真正的字串,順便把反斜線統一成斜線。
    # Windows 的路徑處理只要遇到反斜線就容易出事(它同時是「跳脫字元」),一律換掉最省事。
    return hou.text.expandString(str(path)).replace('\\', '/')


def get_project_name():
    # 目的：從環境變數讀出「現在是哪個專案」。
    # 讀不到就回空字串 —— 這不是錯誤,只代表「沒指定專案」,後面會直接用預設設定。
    return (hou.getenv(ENV_PROJECT, '') or '').strip()


def load_config():
    # 目的：把 JSON 設定檔讀進來,回傳 (設定內容 dict, 這份設定是從哪個檔案來的)。
    #
    # 這個函式的原則是「絕不讓設定檔搞死工具」：
    #   找不到檔案 / JSON 語法打錯 / 內容不是一個 dict → 都只印警告,回傳空 dict,
    #   讓呼叫端直接用內建預設繼續跑。playblast 是個「隨手按一下」的工具,
    #   不該因為設定檔有問題就整個用不了。
    config_path = (hou.getenv(ENV_PROJECT_CONFIG, '') or '').strip()
    if not config_path:
        return {}, ''  # 根本沒設環境變數 → 正常情況,用內建預設

    config_path = expand(config_path)
    if not os.path.isfile(config_path):
        print('    warning : 找不到設定檔 "' + config_path + '",改用內建預設')
        return {}, ''

    try:
        # encoding 明講 utf-8：設定檔裡很可能有中文註解,不指定的話 Windows 會用
        # 系統預設編碼(cp950)去讀,一有中文就直接炸。
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (ValueError, OSError) as e:
        # ValueError = JSON 語法錯(少逗號、多逗號那種);OSError = 檔案讀不到(權限、網路斷)
        print('    warning : 設定檔讀取失敗 "' + config_path + '" : ' + str(e))
        print('              改用內建預設')
        return {}, ''

    if not isinstance(data, dict):
        print('    warning : 設定檔最外層必須是一個 { } 物件,改用內建預設')
        return {}, ''

    return data, config_path


def resolve_settings(config, project):
    # 目的：把三層設定合併成「這次真正要用的那一份」,回傳 (設定 dict, 說明用的來源字串)。
    #
    # 合併順序(後面蓋前面,而且只蓋有寫到的項目)：
    #   1. BUILTIN_DEFAULT      → 保底,每一項都有值
    #   2. config['default']    → 全公司通用預設
    #   3. config['projects'][project] → 這個專案自己的規定
    settings = dict(BUILTIN_DEFAULT)  # 複製一份,不要動到原本的 BUILTIN_DEFAULT
    sources = ['內建預設']

    if not config:
        return settings, ' + '.join(sources)

    # 【極簡寫法支援】
    # 如果 JSON 裡既沒有 "default" 也沒有 "projects",就當作「整份 JSON 本身就是設定」。
    # 這是給「一個專案一個 config 檔」的人用的,不用被迫寫兩層巢狀結構。
    if 'default' not in config and 'projects' not in config:
        settings.update(config)
        sources.append('設定檔(單層寫法)')
        return settings, ' + '.join(sources)

    # 第 2 層
    layer_default = config.get('default')
    if isinstance(layer_default, dict):
        settings.update(layer_default)
        sources.append('設定檔 default')

    # 第 3 層
    projects = config.get('projects')
    if project and isinstance(projects, dict):
        # 大小寫不敏感地找專案：環境變數常常大小寫不一致(shortfilm_a vs SHORT_FILM_A),
        # 為了這種小事讓工具找不到專案太蠢了。
        matched_key = None
        for key in projects:
            if str(key).lower() == project.lower():
                matched_key = key
                break

        if matched_key is None:
            print('    warning : 設定檔裡沒有專案 "' + project + '",只用 default')
        elif isinstance(projects[matched_key], dict):
            settings.update(projects[matched_key])
            sources.append('專案 ' + matched_key)
        else:
            print('    warning : 專案 "' + matched_key + '" 的設定不是 { } 物件,略過')

    return settings, ' + '.join(sources)


def get_scene_viewer():
    # 目的：找到目前的 Scene Viewer(3D 視窗),flipbook 一定要有它才能錄。
    # 找不到就回 None,由呼叫端負責提示使用者。
    return hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)


def get_viewport_camera(viewer):
    # 目的：拿到「目前 viewport 正在看的那台相機」節點。
    # 如果現在是自由視角(persp),camera() 會回 None —— 這不是錯,一樣可以 playblast,
    # 只是檔名裡的 {camera} 會變成 'persp',而且沒有相機解析度可以參考。
    return viewer.curViewport().camera()


def resolve_frame_range(settings):
    # 目的：算出這次要出哪些幀,回傳 (起始幀, 結束幀)。
    # 支援兩種寫法：'playbar' = 跟著播放列  /  [1001, 1100] = 寫死範圍。
    frange = settings.get('frame_range', 'playbar')

    if isinstance(frange, (list, tuple)) and len(frange) == 2:
        return int(frange[0]), int(frange[1])

    if str(frange).lower() != 'playbar':
        print('    warning : frame_range 值看不懂 "' + str(frange) + '",改用 playbar')

    # hou.playbar.frameRange() 回傳的是浮點數,幀號要整數,轉一下。
    start, end = hou.playbar.frameRange()
    return int(start), int(end)


def resolve_resolution(settings, camera):
    # 目的：算出最終的輸出解析度,回傳 (寬, 高)。
    width, height = None, None

    # 優先看要不要沿用相機自己的解析度。
    # 為什麼有這個選項：相機上的 resx/resy 通常才是「這顆鏡頭真正要交的規格」,
    # 讓 playblast 直接跟著它,就不會出現預覽比例跟正式出圖對不上的狀況。
    if settings.get('use_camera_resolution') and camera is not None:
        parm_x = camera.parm('resx')
        parm_y = camera.parm('resy')
        if parm_x is not None and parm_y is not None:
            width, height = int(parm_x.eval()), int(parm_y.eval())

    if not width or not height:
        res = settings.get('resolution', [1920, 1080])
        width, height = int(res[0]), int(res[1])

    # 套用倍率(想快速預覽就設 0.5 出半解析度)
    scale = float(settings.get('resolution_scale', 1.0) or 1.0)
    width = int(width * scale)
    height = int(height * scale)

    # h264 這個編碼器規定寬高必須是偶數,是奇數的話 ffmpeg 會直接失敗。
    # 這裡先無條件修成偶數,免得使用者填了 0.33 倍率之後莫名其妙轉檔失敗。
    width = max(2, width - (width % 2))
    height = max(2, height - (height % 2))
    return width, height


def build_tokens(project, camera):
    # 目的：準備檔名模板 {xxx} 可以用的所有值。
    # 想加新 token(例如 {shot}),在這裡加一行就好,模板那邊就能用了。
    hip_name = os.path.splitext(os.path.basename(hou.hipFile.path()))[0]  # 去掉資料夾和 .hip 副檔名
    return {
        'project': project or 'noproject',
        'hip': hip_name or 'untitled',
        'camera': camera.name() if camera is not None else 'persp',
        'user': getpass.getuser(),
        'date': datetime.datetime.now().strftime('%Y%m%d'),
        # {version} 不在這裡算,因為它要先知道其他 token 才能去掃資料夾,見 resolve_version()
    }


def sanitize(name):
    # 目的：把檔名裡不安全的字元換成底線。
    # hip 檔名/相機名裡可能有空白或奇怪符號,直接拿去當檔名之後餵給 ffmpeg 會很麻煩。
    return re.sub(r'[^A-Za-z0-9._\-]', '_', str(name))


def resolve_version(out_dir, name_template, tokens, ext):
    # 目的：把檔名模板算成最終檔名(不含副檔名),並處理 {version} 自動遞增。
    #
    # 做法：把模板在 {version} 的位置切開,前半段先填好 token 當作「前綴」,
    # 然後去輸出資料夾裡找所有 "前綴 + v數字" 的檔案,取最大的號碼 +1。
    # 這樣就不用自己記上次出到 v幾,也不會不小心蓋掉舊版。
    safe_tokens = {k: sanitize(v) for k, v in tokens.items()}

    if '{version}' not in name_template:
        # 模板沒用到版本號 → 直接填一填就好(代表使用者接受每次覆蓋同一個檔)
        return name_template.format(**safe_tokens)

    prefix = name_template.split('{version}')[0].format(**safe_tokens)
    suffix = name_template.split('{version}')[-1].format(**safe_tokens)

    highest = 0
    pattern = re.compile(re.escape(prefix) + r'v(\d+)', re.IGNORECASE)
    for path in glob.glob(os.path.join(out_dir, prefix + 'v*' + suffix + '.' + ext)):
        match = pattern.match(os.path.basename(path))
        if match:
            highest = max(highest, int(match.group(1)))

    return prefix + 'v' + str(highest + 1).zfill(3) + suffix


def find_ffmpeg(settings):
    # 目的：找到可以用的 ffmpeg.exe,回傳路徑;真的找不到就回 None。
    #
    # 按順序試四個地方,第一個找到的就用：
    #   1. 設定檔裡指定的        → 最明確,優先
    #   2. 環境變數 MIJO_FFMPEG  → 個人機器上的特例
    #   3. Houdini 自己帶的      → $HFS/bin/ffmpeg.exe,大多數 Houdini 安裝都有,不用另外裝
    #   4. 系統 PATH             → 使用者自己裝的
    candidates = []

    if settings.get('ffmpeg'):
        candidates.append(expand(settings['ffmpeg']))

    env_ffmpeg = (hou.getenv(ENV_FFMPEG, '') or '').strip()
    if env_ffmpeg:
        candidates.append(expand(env_ffmpeg))

    hfs = hou.getenv('HFS', '')
    if hfs:
        candidates.append(expand(hfs) + '/bin/ffmpeg.exe')

    for path in candidates:
        if os.path.isfile(path):
            return path

    # shutil.which 會照系統 PATH 去找,找不到回 None
    return shutil.which('ffmpeg')


def esc_drawtext(text):
    # 目的：把要燒進畫面的文字,處理成 ffmpeg drawtext 濾鏡能安全吃下的樣子。
    #
    # 為什麼需要：drawtext 的參數是用 ':' 分隔、用 '\' 跳脫的,
    # 而我們的文字裡很可能有路徑(含 ':')。不處理的話 ffmpeg 會把文字的一部分
    # 當成參數去解析,然後報一個看不懂的錯。
    text = str(text).replace('\\', '/')
    text = text.replace(':', '\\:')   # 冒號跳脫
    text = text.replace("'", '')      # 單引號直接拿掉,跳脫規則太亂,不值得為它處理
    text = text.replace('%', '')      # % 是 drawtext 的展開語法起頭,一般文字裡不該有
    return text


def build_burn_in_filter(settings, tokens, width, height, start_frame):
    # 目的：組出 ffmpeg 的 drawtext 濾鏡字串,把資訊燒在畫面四個角。
    # 字型檔不存在就回空字串(= 不燒字),由呼叫端決定怎麼辦。
    font = expand(settings.get('burn_in_font', ''))
    if not font or not os.path.isfile(font):
        print('    warning : 找不到字型 "' + font + '",這次不燒字幕')
        return ''

    # 字型路徑裡的 'C:' 那個冒號也要跳脫,否則 drawtext 會把 '/Windows/...' 當成下一個參數。
    font_escaped = font.replace('\\', '/').replace(':', '\\:')

    # 字級跟著畫面高度走,這樣出 540p 和出 1080p 的字看起來一樣大。
    size = max(14, int(height / 45))
    pad = max(8, int(height / 60))

    # 共用樣式：白字 + 半透明黑底(box)。有底色才不會在亮畫面上看不到字。
    common = (':fontfile=\'' + font_escaped + '\''
              ':fontsize=' + str(size) +
              ':fontcolor=white'
              ':box=1:boxcolor=black@0.4:boxborderw=' + str(max(3, int(size / 4))))

    left_top = esc_drawtext(tokens['project'] + ' | ' + tokens['hip'])
    right_top = esc_drawtext(tokens['date'] + ' | ' + tokens['user'])
    left_bottom = esc_drawtext('cam ' + tokens['camera'])

    filters = [
        "drawtext=text='" + left_top + "':x=" + str(pad) + ':y=' + str(pad) + common,
        "drawtext=text='" + right_top + "':x=w-tw-" + str(pad) + ':y=' + str(pad) + common,
        "drawtext=text='" + left_bottom + "':x=" + str(pad) + ':y=h-th-' + str(pad) + common,
        # %{frame_num} 是 drawtext 內建的展開語法,配合 start_number 就會印出真正的幀號。
        # 這裡的 % 是刻意要保留的(不能經過 esc_drawtext)。
        "drawtext=text='%{frame_num}':start_number=" + str(start_frame) +
        ':x=w-tw-' + str(pad) + ':y=h-th-' + str(pad) + common,
    ]
    return ','.join(filters)


def run_flipbook(viewer, settings, frame_range, resolution, seq_path):
    # 目的：真的去錄 flipbook,把 viewport 畫面存成圖片序列。
    # 這個呼叫是「阻塞」的:它會卡在這裡直到錄完,所以回來之後序列一定已經存在。
    #
    # .stash() 很重要：它會複製一份目前的 flipbook 設定來改,
    # 這樣我們調的參數不會污染使用者原本在 flipbook 視窗裡設好的東西。
    fb = viewer.flipbookSettings().stash()

    fb.frameRange(frame_range)
    fb.frameIncrement(int(settings.get('frame_step', 1) or 1))
    fb.output(seq_path)
    fb.outputToMPlay(False)          # 不要跳出 MPlay,我們要的是檔案不是預覽視窗
    fb.useResolution(True)           # 不要用 viewport 當下的大小,用我們指定的解析度
    fb.resolution(resolution)
    fb.cropOutMaskOverlay(bool(settings.get('crop_out_view_mask', True)))
    fb.beautyPassOnly(bool(settings.get('beauty_pass_only', True)))

    viewer.flipbook(viewer.curViewport(), fb)


def build_ffmpeg_cmd(ffmpeg, settings, seq_pattern, start_frame, movie_path, vf):
    # 目的：組出完整的 ffmpeg 指令(list 形式),回傳可以直接丟給 subprocess 的東西。
    #
    # 為什麼用 list 不用字串：list 的每個元素會被原封不動當成一個參數,
    # 路徑裡有空白也不會被拆錯,也不用擔心引號怎麼加。
    fmt = str(settings.get('format', 'mp4')).lower()

    cmd = [
        ffmpeg,
        '-y',                                # 目標檔已存在就直接覆蓋,不要停下來問(問了也沒人回答)
        '-framerate', str(settings.get('fps', 25)),  # 輸入序列的幀率
        '-start_number', str(start_frame),   # 序列從第幾號開始(不是從 0)
        '-i', seq_pattern,                   # 輸入,例如 D:/tmp/pb.%04d.jpg
    ]

    if vf:
        cmd += ['-vf', vf]  # 燒字幕的濾鏡

    if fmt == 'mov':
        # ProRes 422 HQ:畫質好、可以再進剪輯,代價是檔案大。
        cmd += ['-c:v', 'prores_ks', '-profile:v', '3', '-pix_fmt', 'yuv422p10le']
    else:
        # h264:通用格式,誰都打得開。
        # yuv420p 這個 pixel format 是為了相容性 —— 不指定的話,從 jpg 轉出來的 mp4
        # 有機率是 yuv444p,QuickTime 跟一堆播放器/瀏覽器會直接播不出來。
        cmd += ['-c:v', 'libx264',
                '-crf', str(settings.get('quality', 20)),
                '-pix_fmt', 'yuv420p']

    # 像素長寬比。一般是 1,做變形寬螢幕才需要。
    aspect = float(settings.get('pixel_aspect', 1.0) or 1.0)
    if abs(aspect - 1.0) > 0.001:
        cmd += ['-aspect', str(aspect)]

    cmd += ['-r', str(settings.get('fps', 25)), movie_path]  # 輸出影片的幀率 + 目標路徑
    return cmd


def run_ffmpeg(cmd, log_path):
    # 目的：跑 ffmpeg,回傳 (成功與否, 結束代碼)。
    #
    # 輸出寫進 log 檔而不是用 PIPE：ffmpeg 話很多,如果用 PIPE 又沒即時去讀,
    # 緩衝區塞滿之後 ffmpeg 會整個卡死不動。寫檔就沒這個問題。
    #
    # CREATE_NO_WINDOW：不要讓黑色的 cmd 視窗閃出來。純視覺問題,但很擾人。
    try:
        with open(log_path, 'wb') as log_handle:
            proc = subprocess.Popen(cmd,
                                    stdout=log_handle,
                                    stderr=subprocess.STDOUT,
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            proc.wait()  # 等它跑完。轉檔通常幾秒,卡一下沒關係,而且我們需要它的結果
    except OSError as e:
        print('!!!! ffmpeg 啟動失敗 : ' + str(e))
        return False, -1

    return proc.returncode == 0, proc.returncode


def ask_overrides(settings, frame_range, resolution, name):
    # 目的：ctrl+click 時跳出來的確認視窗,讓使用者臨時改幾個常改的值。
    # 回傳 (要不要繼續, 幀範圍, 解析度, 檔名)。
    #
    # 這裡改的東西「只對這次有效」,不會寫回設定檔 —— 設定檔是專案規定,
    # 不該被隨手改一下就污染。想永久改就去改 JSON。
    labels = ['幀範圍 (起 結)', '解析度 (寬 高)', '檔名 (不含副檔名)']
    initial = [
        str(frame_range[0]) + ' ' + str(frame_range[1]),
        str(resolution[0]) + ' ' + str(resolution[1]),
        name,
    ]

    button, values = hou.ui.readMultiInput(
        '這次的 playblast 設定 (只對這次有效,不會寫回設定檔)',
        labels,
        initial_contents=initial,
        buttons=('出圖', '取消'),
        default_choice=0,
        close_choice=1,
        title='Playblast',
    )

    if button != 0:
        return False, frame_range, resolution, name

    # 使用者可能亂填,所以每一格都要包 try —— 解析失敗就沿用原本的值,
    # 不要因為一個打錯的字就把整件事取消掉。
    try:
        parts = values[0].split()
        frame_range = (int(parts[0]), int(parts[1]))
    except (ValueError, IndexError):
        print('    warning : 幀範圍看不懂,沿用 ' + str(frame_range))

    try:
        parts = values[1].split()
        resolution = (int(parts[0]), int(parts[1]))
    except (ValueError, IndexError):
        print('    warning : 解析度看不懂,沿用 ' + str(resolution))

    if values[2].strip():
        name = sanitize(values[2].strip())

    return True, frame_range, resolution, name


# functions
##############################################################################################################
# process


def main():
    print('-----------------------------------')
    print('mijo playblast')

    kwargs = get_shelf_kwargs()
    want_dialog = bool(kwargs.get('ctrlclick'))   # ctrl+click  = 出圖前跳確認視窗
    keep_frames = bool(kwargs.get('shiftclick'))  # shift+click = 保留暫存序列

    # ---- 1. 找 Scene Viewer ----
    # flipbook 是「錄 viewport 畫面」,沒有 viewport 就無事可做,直接擋在最前面。
    viewer = get_scene_viewer()
    if viewer is None:
        hou.ui.displayMessage('找不到 Scene Viewer,請先開一個 3D 視窗再執行。')
        return

    # ---- 2. 決定這次要用的設定 ----
    project = get_project_name()
    config, config_path = load_config()
    settings, sources = resolve_settings(config, project)

    print('    專案     : ' + (project or '(未設定 ' + ENV_PROJECT + ')'))
    print('    設定檔   : ' + (config_path or '(未設定 ' + ENV_PROJECT_CONFIG + ')'))
    print('    設定來源 : ' + sources)

    # ---- 3. 把設定換算成具體的數字 ----
    camera = get_viewport_camera(viewer)
    frame_range = resolve_frame_range(settings)
    resolution = resolve_resolution(settings, camera)
    tokens = build_tokens(project, camera)

    out_dir = expand(settings.get('output_dir', '$HIP/playblast'))
    fmt = str(settings.get('format', 'mp4')).lower()

    try:
        os.makedirs(out_dir, exist_ok=True)
    except OSError as e:
        hou.ui.displayMessage('輸出資料夾建立失敗 :\n' + out_dir + '\n\n' + str(e))
        return

    name = resolve_version(out_dir, settings.get('output_name', '{hip}_{version}'),
                           tokens, fmt)

    # ---- 4. ctrl+click:讓使用者臨時微調 ----
    if want_dialog:
        go, frame_range, resolution, name = ask_overrides(
            settings, frame_range, resolution, name)
        if not go:
            print('    使用者取消')
            return

    if frame_range[0] > frame_range[1]:
        hou.ui.displayMessage('幀範圍不合理:起始幀 ' + str(frame_range[0]) +
                              ' 大於結束幀 ' + str(frame_range[1]))
        return

    # ---- 5. 找 ffmpeg ----
    # 先找,不要等 flipbook 出完一百張圖之後才發現沒有 ffmpeg 可以轉檔。
    ffmpeg = find_ffmpeg(settings)
    if not ffmpeg:
        hou.ui.displayMessage(
            '找不到 ffmpeg,無法轉檔。\n\n'
            '解法(擇一):\n'
            '  1. 設定環境變數 ' + ENV_FFMPEG + ' 指到 ffmpeg.exe\n'
            '  2. 在設定檔的 "ffmpeg" 欄位填路徑\n'
            '  3. 把 ffmpeg 加進系統 PATH')
        return

    # ---- 6. 出 flipbook 序列 ----
    # 暫存序列放在輸出資料夾底下的子資料夾,轉完就刪。
    # 放這裡(而不是系統 temp)的好處:萬一轉檔失敗,使用者知道去哪撿那些圖。
    frame_ext = str(settings.get('frame_format', 'jpg')).lower()
    tmp_dir = os.path.join(out_dir, '_tmp_' + name).replace('\\', '/')
    seq_path = tmp_dir + '/' + name + '.$F4.' + frame_ext
    seq_pattern = tmp_dir + '/' + name + '.%04d.' + frame_ext  # ffmpeg 認的是 %04d 不是 $F4

    try:
        os.makedirs(tmp_dir, exist_ok=True)
    except OSError as e:
        hou.ui.displayMessage('暫存資料夾建立失敗 :\n' + tmp_dir + '\n\n' + str(e))
        return

    print('    相機     : ' + tokens['camera'])
    print('    幀範圍   : ' + str(frame_range[0]) + ' - ' + str(frame_range[1]))
    print('    解析度   : ' + str(resolution[0]) + ' x ' + str(resolution[1]))
    print('    出圖中...(Houdini 會卡住一下,正常)')

    try:
        run_flipbook(viewer, settings, frame_range, resolution, seq_path)
    except hou.Error as e:
        hou.ui.displayMessage('flipbook 失敗 :\n' + str(e))
        return

    # flipbook 跑完不代表有東西 —— 使用者可能中途按 esc 取消。檢查一下再繼續。
    frames = glob.glob(tmp_dir + '/*.' + frame_ext)
    if not frames:
        hou.ui.displayMessage('沒有出到任何圖(可能是中途取消了)。\n暫存資料夾:\n' + tmp_dir)
        return
    print('    出圖完成 : ' + str(len(frames)) + ' 幀')

    # ---- 7. 轉檔 ----
    movie_path = out_dir + '/' + name + '.' + fmt
    log_path = tmp_dir + '/_ffmpeg_log.txt'

    vf = ''
    if settings.get('burn_in'):
        vf = build_burn_in_filter(settings, tokens, resolution[0], resolution[1],
                                  frame_range[0])

    print('    轉檔中...')
    cmd = build_ffmpeg_cmd(ffmpeg, settings, seq_pattern, frame_range[0],
                           movie_path, vf)
    ok, code = run_ffmpeg(cmd, log_path)

    # 燒字幕是這裡最脆弱的一環(字型、跳脫字元、ffmpeg 版本都可能出事)。
    # 與其讓整個 playblast 白做,不如把字幕丟掉再轉一次 —— 沒字幕的影片還是有用的。
    if not ok and vf:
        print('    warning : 帶字幕轉檔失敗(exit code=' + str(code) + '),改用不燒字幕重試')
        cmd = build_ffmpeg_cmd(ffmpeg, settings, seq_pattern, frame_range[0],
                               movie_path, '')
        ok, code = run_ffmpeg(cmd, log_path)

    if not ok:
        hou.ui.displayMessage('ffmpeg 轉檔失敗 (exit code=' + str(code) + ')\n\n'
                              '詳細訊息:\n' + log_path + '\n\n'
                              '暫存序列保留在:\n' + tmp_dir)
        print('!!!! 轉檔失敗,暫存序列保留在 ' + tmp_dir)
        return

    # ---- 8. 收尾 ----
    if keep_frames:
        print('    暫存序列保留 (shift+click) : ' + tmp_dir)
    else:
        # ignore_errors=True:刪不掉就算了。影片已經出好了,為了刪不掉暫存檔而報錯很沒必要
        # (常見原因:log 檔還被別的程式開著)。
        shutil.rmtree(tmp_dir, ignore_errors=True)

    print('    完成     : ' + movie_path)
    print('-----------------------------------')

    if settings.get('open_after'):
        try:
            os.startfile(movie_path.replace('/', '\\'))  # Windows 專用:用系統預設程式開檔
        except OSError as e:
            print('    warning : 自動開檔失敗 : ' + str(e))


# 這支腳本被 shelf 工具載入(reload)後會直接執行 main(),所以最後直接呼叫它。
main()

# process
