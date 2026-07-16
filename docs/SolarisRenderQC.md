# Solaris 渲染檢查（SolarisRenderQC）

出圖前按一下，把 render 節點的最基礎設定體檢一遍：**camera、輸出路徑、解析度、幀範圍**。

對應腳本：`shelf_by_python/shelf_Solaris_render_QC.py`
Shelf 工具名稱：**渲染检查**

---

## 這個工具解決什麼問題

在 Solaris 裡設好 Karma / Redshift / Arnold，按下 render 丟去農場，跑了兩小時才發現：camera 根本沒指定、輸出路徑少了 `$F4` 導致每一幀互相覆蓋、或路徑寫在自己電腦的 `C:\` 農場機器讀不到。

這些都是「早該一眼看出來」的低級錯誤，但人在趕工的時候就是會漏。這個工具把它們變成一個按鍵：抓出場景裡的 render 節點，逐項檢查，在 console 印報告，順便把有問題的項目寫進節點 comment 直接標在網路圖上。

它**只做最基礎的 QC**，不會幫你看畫面對不對、材質有沒有掉。目標是三秒內跑完，不是取代人眼。

---

## 安裝

1. 確認 `shelf_by_python/` 在 Houdini 的 `PYTHONPATH` 裡（所有工具共用同一個前提）。
2. 確認 `toolbar/mijo_tools.shelf` 有被 Houdini 載入。
3. 裝好就能用。但如果你們團隊有「成果一律寫到某台伺服器」的規定，建議先設定 `ALLOWED_OUTPUT_ROOTS`（見下面「設定項」），否則路徑白名單這項不會生效。

---

## 使用方式

| 操作 | 結果 |
|---|---|
| 什麼都不選 → 按工具 | 掃描 `/stage` 和 `/out` 底下所有認得的 render 節點 |
| 選取節點 → 按工具 | 只檢查選取的那幾個 |
| ctrl + click 工具 | 深度檢查（會 cook stage，比較慢但最準） |

一般出圖前的流程就是「什麼都不選，按一下，看 console」。

---

## 快速檢查 vs 深度檢查

這是這個工具最主要的設計取捨，值得花三十秒理解。

**預設是快速檢查**：只讀參數字串，完全不碰 `node.stage()`，所以不會觸發 LOP cook。大場景也是瞬間跑完。代價是它無法確認「camera 這個 prim 到底在不在 stage 上」——它只能看出你有沒有填、格式對不對。

**ctrl+click 是深度檢查**：真的去 cook stage，把 camera prim 找出來，確認它存在、而且型別真的是 `Camera`（指到 Xform 或 Mesh 是常見錯誤，通常是選錯層級選到相機的爸爸）。缺點是場景大的時候 cook 可能要等好幾秒甚至更久。

要確認 prim 存在，除了 cook 沒有別的方法——這是 USD 的本質，不是偷懶。所以工具把選擇權交給你：平常快速跑，真的要送農場前 ctrl+click 跑一次完整的。

---

## 報告怎麼看

console 輸出長這樣：

```
-----------------------------------
Solaris Render QC
沒有選取節點 → 掃描 /stage 與 /out
模式 : 快速檢查(不 cook stage / ctrl+click 可做深度檢查)

[ERROR] /stage/karma1  (Karma (LOP))
    ERROR : camera : 沒有指定相機
    WARN : resolution : 有奇數邊長，之後轉 mp4 可能會出問題

[OK] /stage/usdrender_rop1  (USD Render ROP)
    OK : camera : /cameras/camMain
    OK : output : $HIP/render/shot010.$F4.exr
    OK : resolution : 1920 x 1080
    OK : frames : 1 - 240

-----------------------------------
檢查完成 : 1 個 ERROR / 0 個 WARN / 1 個通過 / 3 個略過(不是 render 節點)
!! 有 ERROR，出圖前請先修掉 !!
-----------------------------------
```

節點開頭的 `[ERROR]` / `[WARN]` / `[OK]` 是**整個節點的總評**，取最嚴重的那一項。

注意 OK 的項目**只在整個節點通過時才會印**。節點一旦有問題，報告就只列出問題項——否則真正的錯誤會被一堆 OK 洗版，那就失去意義了。

### 三種等級

| 等級 | 意思 |
|---|---|
| `ERROR` | 幾乎確定出不了圖，或出來的東西是壞的。一定要修 |
| `WARN` | 不一定是錯，但很可疑，請自己確認一下 |
| `OK` | 這項通過 |

`WARN` 存在的理由是避免假警報。例如「輸出資料夾不存在」——多數 renderer 會自己建資料夾，所以通常沒事，但也可能是你路徑打錯字。這種情況報 ERROR 只會讓人習慣性忽略報告，久了整個工具就沒用了。

### comment 標記

`WRITE_TO_COMMENT` 開啟時（預設開），有問題的節點 comment 會被寫成：

```
[QC] ERROR
ERROR : camera : 沒有指定相機
WARN : resolution : 有奇數邊長，之後轉 mp4 可能會出問題
```

下次檢查通過時，工具會把它清掉——但**只清開頭是 `[QC]` 的 comment**。你自己手寫的 comment 不會被動到。

---

## 檢查了哪些項目

### camera

| 情況 | 等級 |
|---|---|
| 沒有指定相機 | ERROR |
| 不是合法的 USD prim path（沒有以 `/` 開頭） | ERROR |
| stage 上找不到這個 prim（**僅深度模式**） | ERROR |
| 找到了但型別不是 `Camera`（**僅深度模式**） | ERROR |
| 參數是灰的（override 開關沒打開） | OK，跳過檢查 |

最後那條很重要：很多 override 參數前面有個 toggle，開關沒打開時參數是灰的。灰掉的參數就算是空的也不是錯誤——使用者本來就沒打算用它，上游的設定會生效。

### output（輸出路徑）

| 情況 | 等級 |
|---|---|
| 路徑是空的 | ERROR |
| 算序列但路徑沒有 `$F` | ERROR |
| 路徑沒有副檔名 | ERROR |
| 寫在本機硬碟（`C:` / `D:`） | ERROR |
| 不在 `ALLOWED_OUTPUT_ROOTS` 白名單底下 | ERROR |
| 副檔名不在允許清單內 | WARN |
| 輸出資料夾不存在 | WARN |
| 資料夾檢查失敗（網路斷線 / 權限不足） | WARN |

「算序列但沒有 `$F`」是最經典的災難：每一幀都寫到同一個檔名，前面算的被後面蓋掉，兩小時後只剩最後一幀。工具會先看 `trange`，只算單幀時這項不檢查（`$F` 本來就沒意義）。

本機硬碟檢查是用**展開後**的路徑判斷的。因為 `$HIP` 本身就可能展開成 `C:\...`，只看原始字串是看不出來的。

只檢查資料夾，不檢查檔案——檔案本來就還沒算出來。

### resolution（解析度）

| 情況 | 等級 |
|---|---|
| 0 或負數 | ERROR |
| 小於 `MIN_RESOLUTION`（預設 64） | WARN |
| 有奇數邊長 | WARN |
| 參數是灰的（使用相機設定） | OK，跳過檢查 |

「太小」抓的是「測試時調成 320，出圖前忘了調回來」。奇數邊長的問題是 h264/h265 這類編碼器要求偶數，後製轉檔時會失敗或被硬裁一個 pixel。

### frames（幀範圍）

| 情況 | 等級 |
|---|---|
| 起始幀大於結束幀 | ERROR |
| `trange = 0`（只算目前這一幀） | WARN |
| frame step 不是 1 | WARN |

幀範圍錯了不會讓 render 失敗，它會**安靜地算出錯的東西**——這種最可怕，所以即使是「只算當前幀」這種合法設定也給了 WARN。跳幀有時是故意的（算 preview），但更常是忘了改回來。

---

## 支援哪些節點

由 `RENDER_NODE_RULES` 這張對照表決定，用型別名稱**開頭比對**：

| 節點型別（開頭比對） | 顯示名稱 |
|---|---|
| `karma` | Karma (LOP) |
| `usdrender_rop` | USD Render ROP |
| `usdrender` | USD Render |
| `rendersettings` | Render Settings (LOP) |
| `renderproduct` | Render Product (LOP) |
| `Redshift_ROP` | Redshift |
| `arnold` | Arnold |

不在表上的節點會被靜靜略過，只在最後的統計數字裡出現（「N 個略過」）。

`rendersettings` 本身不出圖（輸出路徑在 `renderproduct` 上），所以它的 output 檢查是空的；`renderproduct` 反過來，只檢查 output 不檢查 camera。

### 加一個新的 renderer

在 `RENDER_NODE_RULES` 加一筆，檢查邏輯完全不用動：

```python
{
    'prefix':     '你的型別名稱開頭',
    'label':      '報告上要顯示的名稱',
    'camera':     ['相機參數名', '備用名稱'],
    'output':     ['輸出參數名'],
    'res_x':      ['寬度參數名'],
    'res_y':      ['高度參數名'],
},
```

每個欄位都是**候選名稱的清單**，由左往右找，用第一個真的存在的。為什麼不是單一名稱？因為同一個節點不同版本可能改過參數名，多列幾個候選比較耐命，猜錯一個也不會整個失效。用不到的欄位就給空 list。

不知道型別名稱和參數名稱？選取那個節點，在 Houdini 的 Python Shell 貼：

```python
n = hou.selectedNodes()[0]
print(n.type().name())                        # 型別名稱
print([p.name() for p in n.parms()])          # 所有參數名稱
```

順序有意義，由上往下找，第一個對上的就用。所以 `usdrender_rop` 要放在 `usdrender` 前面——否則前者永遠會被後者攔截。

### 加一個新的檢查項目

寫一個同樣格式的函式，加進 `ALL_CHECKS`：

```python
def check_something(node, rule, deep):
    # 回傳 [(等級, 訊息), ...]
    return [('WARN', 'something : 有點怪')]

ALL_CHECKS = [
    check_camera,
    check_output,
    check_resolution,
    check_frame_range,
    check_something,   # <- 加這行
]
```

函式吃 `(node, rule, deep)`，回傳 `[(等級, 訊息), ...]`。`deep` 是布林值，代表現在是不是深度模式——會 cook stage 的檢查請放在 `if not deep: return` 後面。回傳空 list 代表「這個節點不適用這項檢查」。

單項檢查爆掉不會拖垮其他項目，會在報告裡變成一行 `WARN : check_xxx 檢查失敗 : ...`。

---

## 設定項

腳本開頭的「手動設定區」：

| 變數 | 預設 | 作用 |
|---|---|---|
| `ALLOWED_OUTPUT_ROOTS` | `[]` | 輸出路徑必須在這些根目錄底下。留空 = 不檢查這項 |
| `LOCAL_DRIVERS` | `['C:', 'D:']` | 這些磁碟機上的輸出路徑會報 ERROR |
| `ALLOWED_IMAGE_EXTS` | `.exr .png .jpg .jpeg .tif .tiff` | 不在清單內的副檔名會報 WARN |
| `CHECK_OUTPUT_DIR` | `True` | 要不要檢查輸出資料夾存不存在。路徑在網路磁碟時可能有延遲，覺得卡就改 `False` |
| `MIN_RESOLUTION` | `64` | 低於這個值的解析度會報 WARN |
| `WRITE_TO_COMMENT` | `True` | 要不要把結果寫進節點 comment |

`ALLOWED_OUTPUT_ROOTS` 預設留空，因為每個團隊的規則不一樣。要用的話：

```python
ALLOWED_OUTPUT_ROOTS = ['P:/', 'Z:/projects/']
```

比對時會把反斜線正規化成正斜線、並轉小寫，所以 `P:\prj\...` 和 `p:/prj/...` 都會對上。

---

## 疑難排解

**Arnold 節點報「檢查失敗」或參數抓不到**
Arnold（HtoA）的 Solaris ROP 參數命名沒有在實機上驗證過，表裡的候選名稱是推測的。請用上面「加一個新的 renderer」那段的 Python Shell 指令把實際參數名印出來，補進 `RENDER_NODE_RULES` 的 `arnold` 那一筆。

**明明設好了卻報 ERROR: camera 沒有指定相機**
確認你看的是不是同一個節點——Karma LOP 和它上游的 Render Settings LOP 都有 camera 參數。也確認那個參數不是灰的（灰的話工具會跳過並顯示「未啟用 override」，不會報錯）。

**深度檢查很慢**
那就是 cook 本身的時間，工具沒辦法加速它。平常用快速模式，只在要送農場前 ctrl+click 一次。

**報告說 stage 上找不到 camera，但我在 viewport 看得到**
檢查是在**節點自己的 stage** 上做的，不是最終的 stage。如果相機是在這個 render 節點的**下游**才被建出來或改名，這裡當然找不到。這種情況通常代表節點接線順序有問題。

**按工具沒反應，console 說 `NameError: reload`**
`reload()` 在 Python 3 已經不是 builtin 了。在 shelf script 開頭加 `from importlib import reload` 即可。這是所有工具共通的問題，不是這支獨有的。

**節點 comment 被工具蓋掉了**
只有開頭是 `[QC]` 的 comment 會被清除。如果你的 comment 剛好是 `[QC]` 開頭，改掉開頭，或把 `WRITE_TO_COMMENT` 設成 `False`。

---

## 已知限制

- **這支腳本沒有在 Houdini 實機上跑過**（開發環境沒有 Houdini），邏輯是照 API 文件寫的。第一次使用請先在測試場景跑過。Arnold 的參數名尤其不確定，見「疑難排解」。
- 只檢查**最基礎**的項目。畫面對不對、材質掉沒掉、AOV 齊不齊、光有沒有開，都不在範圍內。通過檢查不等於出得了圖。
- 快速模式**無法**確認 camera prim 真的存在——它只看得出「你有沒有填」和「格式對不對」。要確認請用深度模式。
- 只掃 `/stage` 和 `/out`。render 節點藏在別的地方（例如包在 subnet 外的其他 context）就要手動選取。
- 只支援 Windows 的路徑慣例（磁碟機代號）。`LOCAL_DRIVERS` 和根目錄白名單在 Linux 農場上要自己改。
- `CHECK_OUTPUT_DIR` 在網路磁碟上有可能造成介面短暫延遲，因為它會實際去戳檔案系統。
