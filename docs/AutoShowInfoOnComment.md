# 自動顯示節點資訊（AutoShowInfoOnComment）

把節點的重點資訊（路徑、幀範圍、檔案在不在）直接顯示在節點旁邊，而且**參數一改就自動更新**。

對應腳本：`shelf_by_python/shelf_Auto_show_info_on_comment.py`
Shelf 工具名稱：**自动显示注释信息**

---

## 這個工具解決什麼問題

網路裡一堆 `fetch`、`filecache`、`file` 節點，光看節點名字根本不知道它讀寫哪個路徑。每次都要點進去看參數，很煩。

這個工具把那些資訊寫進節點的 comment，並打開 comment 顯示旗標，讓它直接浮在節點旁邊。更重要的是它會幫節點掛一個「參數變更回呼」，所以之後你改參數，comment 會自己跟著改，不用再按一次工具。

---

## 安裝

1. 確認 `shelf_by_python/` 在 Houdini 的 `PYTHONPATH` 裡（三個工具共用同一個前提）。
2. 確認 `toolbar/mijo_tools.shelf` 有被 Houdini 載入。
3. 不需要任何環境變數或額外設定，裝好就能用。

---

## 使用方式

| 操作 | 結果 |
|---|---|
| 選取節點 → 按工具 | 開啟資訊顯示，並開始即時更新 |
| 對「已開啟」的節點再按一次 | 關閉（toggle），comment 會被清空 |
| ctrl + click 工具 | 強制關閉選取節點的資訊顯示 |
| 什麼都不選 → 按工具 | 刷新場景裡所有已開啟的節點 |

最後那個「什麼都不選」是備援用的。正常情況 callback 會自動更新，不需要手動刷新；但有一種情況它幫不上忙——快取在別的地方被算好了，而節點參數從頭到尾沒動過，這時 callback 不會被觸發，comment 上的「檔案存不存在」就還是舊的。這時候取消選取、按一下工具，就能全部重算。

---

## comment 上會顯示什麼

以一個 `filecache` 節點為例：

```
cache Path :
$HIP/geo/mycache.$F4.bgeo.sc
-> H:/prj/shot010/geo/mycache.0032.bgeo.sc
frames : 1 - 240
status : dir OK (this frame not found)
```

逐行說明：

- **第一行**是標題，會依節點型別不同而變（`fetch Path`、`SOP Output`、`Redshift Output`…）。
- **第二行**是參數的原始字串，`$HIP`、`$F4` 都還在。這是給人看的，比較容易理解意圖。
- **第三行**（`->` 開頭）是展開後的真實路徑。**兩者相同時這行不會出現**，例如路徑裡根本沒有變數。
- **frames** 只在節點的 `trange` 不是「current frame」時才出現。
- **status** 有四種值，見下表。

### status 的四種狀態

| 顯示 | 意思 |
|---|---|
| `file OK` | 檔案確實存在 |
| `dir OK (this frame not found)` | 資料夾在，但目前這一幀的檔案不在 |
| `!! NOT FOUND !!` | 連資料夾都不存在，通常代表根本還沒算過 |
| `?? (check failed)` | 檢查失敗，例如網路斷線或權限不足 |

`dir OK (this frame not found)` 是序列檔的常態，不一定是錯的。因為展開後的路徑只會是「目前這一幀」，你可能只是還沒跳到已經算好的那幾幀。

### fetch 節點的特殊處理

`fetch` 的 `source` 參數指的是**另一個 ROP 節點的路徑**，不是檔案路徑。光看到 `/out/geo1` 其實還是不知道它會寫去哪，所以工具會多跑一步，把目標節點找出來，順便把它的輸出路徑也一起列出來：

```
fetch Path :
/out/geo1

SOP Output :
$HIP/geo/`$OS`.$F4.bgeo.sc
```

---

## 支援哪些節點

由 `PATH_PARM_RULES` 這張對照表決定：

| 節點型別（開頭比對） | 讀取的參數 | comment 標題 |
|---|---|---|
| `fetch` | `source` | fetch Path |
| `filecache` | `file` | cache Path |
| `file` | `file` | file Path |
| `rop_geometry` | `sopoutput` | SOP Output |
| `geometry` | `sopoutput` | SOP Output |
| `rop_alembic` | `filename` | ABC Output |
| `alembic` | `fileName` | ABC Path |
| `ifd`（Mantra） | `vm_picture` | Mantra Output |
| `Redshift_ROP` | `RS_outputFileNamePrefix` | Redshift Output |
| `arnold` | `ar_picture` | Arnold Output |
| `karma` | `picture` | Karma Output |
| `opengl` | `picture` | OpenGL Output |
| `usd` | `lopoutput` | USD Output |
| `comp` | `copoutput` | COP Output |
| `object_merge` | `objpath1` | Merge From |

選到不在表上的節點，工具會在 console 印一行 `skip : "xxx" (型別) 沒有支援的路徑參數` 然後跳過，不會掛 callback 上去白費工。

### 加一個新節點

在腳本的 `PATH_PARM_RULES` 加一行就好，程式碼完全不用動：

```python
PATH_PARM_RULES = [
    ('fetch', 'source', 'fetch Path'),
    ('你的型別名稱開頭', '參數名稱', '要顯示的標題'),   # <- 加這行
    ...
]
```

三個欄位分別是：型別名稱的**開頭**、要讀的參數名稱、顯示在 comment 上的標題。

不知道型別名稱和參數名稱？選取那個節點，在 Houdini 的 Python Shell 貼：

```python
n = hou.selectedNodes()[0]
print(n.type().name())                        # 型別名稱
print([p.name() for p in n.parms()])          # 所有參數名稱
```

順序有意義，由上往下找，第一個對上的就用。所以比較specific的規則要放在前面。

---

## 設定項

腳本開頭的「手動設定區」有三個開關：

| 變數 | 預設 | 作用 |
|---|---|---|
| `USER_DATA_KEY` | `'mijo_auto_info'` | 節點上的標記名稱，除非跟別的工具撞名，否則別動 |
| `CHECK_FILE_EXISTS` | `True` | 要不要檢查檔案存不存在。路徑在網路磁碟時這個檢查可能有延遲，覺得卡就改 `False` |
| `SHOW_EXPANDED_PATH` | `True` | 要不要顯示展開後的路徑（`->` 那行） |

---

## 運作原理

這段是給想改腳本的人看的，只是要用的話可以跳過。

### 為什麼需要 callback 才能「即時」

Houdini 的 comment 欄位只吃純文字，**不能像參數那樣寫表達式**，所以它不會自己更新。唯一能做到即時的方法，就是請 Houdini 在「這個節點的參數被改動時」通知我們，我們收到通知再把 comment 重寫一次：

```python
node.addEventCallback((hou.nodeEventType.ParmTupleChanged,), on_node_changed)
```

### 為什麼需要 user data 標記

callback 只是 Python 記憶體裡的東西，**存檔時不會被存進 hip**。所以工具額外在節點上寫一個 user data 當標記（user data 會跟著 hip 存檔）：

```python
node.setUserData('mijo_auto_info', '1')
```

開檔後再靠 `hou.hipFile.addEventCallback` 監聽 `AfterLoad`，依標記把 callback 重新掛回去。這樣「開著的節點」存檔重開後仍然是開著的。

也因為狀態是存在 user data，`is_watched()` 判斷開/關才能跨 session 正確運作。

### 為什麼拆 callback 是用「函式名稱」比對

```python
if getattr(callback, '__name__', '') == 'on_node_changed':
    node.removeEventCallback(event_types, callback)
```

這裡看起來很怪，但有原因。這支腳本是靠 `reload()` 重新載入的，reload 之後模組裡的 `on_node_changed` 會變成一個**全新的函式物件**，跟先前掛上去的那個舊物件不是同一個東西。所以不能寫成 `removeEventCallback(on_node_changed)`——拿新的去比對根本對不上，舊的永遠拆不掉，每按一次工具就多掛一個。

函式**名稱**在 reload 前後是一樣的，所以改用名稱比對。`hou.hipFile` 那邊的 callback 也是同樣的處理。

### 型別判斷為什麼用 startswith

Houdini 的型別名稱常常帶版本號，例如 `filecache::2.0`。用開頭比對，之後 SideFX 出 `filecache::3.0` 這支腳本也還能用。

（舊版曾經寫成 `str(n.type()) == '<hou.NodeType for Driver fetch>'`，那是拿給人看的除錯字串在比對，SideFX 隨時可以改格式，改了就整個失效。已經改掉了。）

---

## 疑難排解

**改了參數但 comment 沒更新**
先確認那個節點真的是「開啟」狀態（有沒有 comment 浮在旁邊）。如果 Houdini 中途重開過、或腳本報錯過，callback 可能掉了——重選節點按兩次工具（關掉再開）即可重掛。

**Houdini 重開後就不會自動更新了**
`AfterLoad` 的重掛邏輯是寫在這支腳本裡的，而腳本要「被 import 過」才存在。所以每次 Houdini 開起來，**第一次**開檔前如果沒按過工具，callback 不會自動接回。按一次工具（什麼都不選也行）就會登記好，之後同一個 session 內開的檔都正常。想徹底解決的話，可以在 `456.py` 或 `pythonrc.py` 裡 import 這支腳本。

**按工具沒反應，console 說 `NameError: reload`**
`reload()` 在 Python 3 已經不是 builtin 了。在 shelf script 開頭加 `from importlib import reload` 即可。這是三個工具共通的問題，不是這支獨有的。

**節點被跳過了**
console 會印 `skip : ... 沒有支援的路徑參數`。到 `PATH_PARM_RULES` 加一行（見上面「加一個新節點」）。

**status 一直是 `?? (check failed)`**
通常是網路磁碟斷線或權限問題。不影響路徑顯示，如果不在意可以把 `CHECK_FILE_EXISTS` 改成 `False` 關掉檢查。

---

## 已知限制

- comment 是純文字，**沒有顏色、不能點擊**。這是 Houdini comment 本身的限制。
- 只監聽「參數變更」。節點被改名、或檔案在 Houdini 外面被算出來，都不會觸發更新（用「什麼都不選 → 按工具」手動刷新）。
- `CHECK_FILE_EXISTS` 在網路磁碟上有可能造成介面短暫延遲，因為它會實際去戳檔案系統。
- 關閉時會把 comment 直接清空。**如果你自己在那個節點的 comment 寫過東西，會被蓋掉。**
