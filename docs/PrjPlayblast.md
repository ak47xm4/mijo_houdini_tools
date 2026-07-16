# 專案預覽（PrjPlayblast）

按一下，就用「這個專案的規定」出一段預覽影片：**自動出圖 → 自動轉 mp4 → 自動命名（含版本號）→ 自動開起來看**。

對應腳本：`shelf_by_python/shelf_prj_playblast.py`
設定檔範例：`config/project_config.example.json`
Shelf 工具名稱：**专案预览**

---

## 這個工具解決什麼問題

想快速出一段東西給人看，現在的流程是：開 flipbook 視窗、手動填解析度、手動填幀範圍、手動選資料夾、出完一堆 jpg、再開別的軟體轉 mp4、再自己想檔名、再自己記得這次是 v3 還是 v4。每次都重來一遍，而且很容易填錯。

這個工具的想法是：**解析度多少、幀率多少、檔案放哪，不該是你每次填的東西，而是「這個專案本來就規定好」的**。工具去查專案設定檔拿。換專案 = 換一個環境變數，設定自動跟著換。

---

## 安裝

1. 確認 `shelf_by_python/` 在 Houdini 的 `PYTHONPATH` 裡（所有工具共用同一個前提）。
2. 確認 `toolbar/mijo_tools.shelf` 有被 Houdini 載入。
3. **不設定任何環境變數也能直接用** —— 會用腳本內建的預設（1920x1080 / 25fps / 存在 `$HIP/playblast`）。想要專案化再往下看。

---

## 使用方式

| 操作 | 結果 |
|---|---|
| 直接 click | 用專案設定直接出圖，全自動 |
| ctrl + click | 出圖前跳一個視窗，可以臨時改幀範圍 / 解析度 / 檔名 |
| shift + click | 保留中間產生的 jpg 序列不刪 |

出圖時 Houdini 會卡住一下（flipbook 是同步的），這是正常的。進度在 console。

---

## 專案化：兩個環境變數

| 環境變數 | 值 | 沒設會怎樣 |
|---|---|---|
| `MIJO_PROJECT` | 專案代號，例如 `SHORT_FILM_A` | 用通用預設，不查專案 |
| `MIJO_PROJECT_CONFIG` | JSON 設定檔的完整路徑 | 用腳本內建預設 |
| `MIJO_FFMPEG` | ffmpeg.exe 路徑（通常不用設） | 自動找，見下面 |

設定方式擇一：

- Windows 系統環境變數
- Houdini 的 `houdini.env` 加一行：`MIJO_PROJECT = "SHORT_FILM_A"`

腳本用 `hou.getenv` 讀，兩種設法都抓得到。

環境變數的**名字**如果跟你們公司既有的命名對不上（例如你們叫 `SHOW`），改腳本頂端的 `ENV_PROJECT` 那幾行就好，不用動下面的程式。

---

## 設定是怎麼被決定的：三層覆蓋

這是整個工具的核心，值得花三十秒理解。

```
第 1 層：腳本裡的 BUILTIN_DEFAULT   ← 保底，每一項都有值（這就是「簡單版」）
第 2 層：JSON 的 "default"          ← 全公司通用預設
第 3 層：JSON 的 "projects"[你的專案] ← 這個專案自己的規定
```

**後面蓋前面，而且只蓋「有寫到的那幾項」。** 所以專案底下只需要寫跟 default 不一樣的地方，不用整份抄。例如專案只寫了 `resolution`，那 `fps` 就還是沿用第 2 層的值。

這個設計的重點在**保底**：config 檔不見了、專案名沒設、JSON 打錯逗號，工具都只會印個 warning 然後退回內建預設繼續跑，不會整個用不了。playblast 是隨手按一下的工具，不該因為設定檔有問題就卡住你。

### 極簡寫法

如果你想「一個專案一個 config 檔」，可以不要 `default` / `projects` 這兩層，整個 JSON 直接就是設定本身：

```json
{ "resolution": [2048, 858], "fps": 24, "output_dir": "P:/myprj/playblast" }
```

腳本偵測到最外層沒有 `default` 也沒有 `projects`，就會這樣解讀。

---

## 設定項

複製 `config/project_config.example.json` 改成自己的。

### 畫面

| 項目 | 預設 | 說明 |
|---|---|---|
| `resolution` | `[1920, 1080]` | 輸出解析度 `[寬, 高]` |
| `resolution_scale` | `1.0` | 再乘一個倍率。`0.5` = 半解析度預覽，算很快 |
| `use_camera_resolution` | `false` | `true` = 忽略 `resolution`，改用 viewport 相機自己的 `resx`/`resy` |
| `pixel_aspect` | `1.0` | 像素長寬比。做變形寬螢幕（anamorphic）才會不是 1 |

`use_camera_resolution` 值得考慮打開：相機上的 `resx`/`resy` 通常才是「這顆鏡頭真正要交的規格」，跟著它走就不會出現預覽比例跟正式出圖對不上。

### 時間

| 項目 | 預設 | 說明 |
|---|---|---|
| `fps` | `25` | 影片幀率 |
| `frame_range` | `"playbar"` | `"playbar"` = 跟著播放列；或寫 `[1001, 1100]` 指定 |
| `frame_step` | `1` | 每幾幀出一張。`2` = 隔幀出，快一倍但會頓 |

### 輸出

| 項目 | 預設 | 說明 |
|---|---|---|
| `output_dir` | `"$HIP/playblast"` | 可以用 `$HIP`、`$JOB` 這種 Houdini 變數 |
| `output_name` | `"{hip}_{camera}_{version}"` | 檔名模板，token 見下 |
| `format` | `"mp4"` | `mp4`（h264，小、通用）或 `mov`（ProRes 422 HQ，畫質好、大） |
| `quality` | `20` | 只對 mp4 有效。ffmpeg 的 crf，越小畫質越好檔案越大（18~23 常用） |

### 出圖細節

| 項目 | 預設 | 說明 |
|---|---|---|
| `frame_format` | `"jpg"` | 中間暫存序列格式。jpg 最快，想無損填 `"png"` |
| `beauty_pass_only` | `true` | 不畫格線/操作把手，只留畫面本身 |
| `crop_out_view_mask` | `true` | 直接裁掉相機遮罩外的黑邊 |

### 附加

| 項目 | 預設 | 說明 |
|---|---|---|
| `burn_in` | `true` | 在畫面四角燒專案/檔名/日期/使用者/相機/幀號 |
| `burn_in_font` | `"C:/Windows/Fonts/consola.ttf"` | 燒字用的字型檔 |
| `open_after` | `true` | 轉檔完自動用系統預設播放器開 |
| `ffmpeg` | `""` | ffmpeg.exe 路徑，留空 = 自動找 |

---

## 檔名 token

`output_name` 裡可以用這些 `{xxx}`：

| token | 展開成 |
|---|---|
| `{project}` | `MIJO_PROJECT` 的值，沒設就是 `noproject` |
| `{hip}` | hip 檔名（不含副檔名） |
| `{camera}` | viewport 相機名。自由視角時是 `persp` |
| `{user}` | 目前登入的使用者 |
| `{date}` | 今天，`20260717` 格式 |
| `{version}` | `v001`、`v002`... 自動遞增 |

`{version}` 的做法是：把模板在 `{version}` 的位置切開，拿前半段當前綴，去輸出資料夾裡找所有 `前綴 + v數字` 的檔案，取最大的號碼 +1。所以你不用記上次出到 v 幾，也不會不小心蓋掉舊版。

模板裡**不寫** `{version}` 也可以 —— 那就是每次覆蓋同一個檔。

想加新 token（例如 `{shot}`），在腳本的 `build_tokens()` 加一行就好。

---

## ffmpeg 是怎麼找到的

按順序試四個地方，第一個找到的就用：

1. 設定檔的 `"ffmpeg"` 欄位
2. 環境變數 `MIJO_FFMPEG`
3. **`$HFS/bin/ffmpeg.exe`** —— Houdini 自己帶的，大多數安裝都有，所以通常不用另外裝
4. 系統 `PATH`

四個都沒有才會跳錯誤視窗。這個檢查是在出圖**之前**做的，不會讓你等出完一百張圖才發現沒 ffmpeg。

---

## 設計上的取捨

**為什麼用 flipbook 而不是 opengl ROP**：flipbook 是所見即所得，你 viewport 看到什麼就錄到什麼，跟你手動做的行為一致。opengl ROP 有自己的一套設定（burn-in、背景圖），不需要 viewport，比較適合批次/農場——列在 roadmap 的 future features 裡，之後可以做成 config 可切換的 backend。

**為什麼燒字幕失敗會自動重試**：burn-in 是整條流程裡最脆弱的一環（字型路徑、drawtext 的跳脫字元、ffmpeg 版本都可能出事）。與其讓整個 playblast 白做，不如把字幕丟掉再轉一次——沒字幕的影片還是有用的。console 會告訴你發生了什麼。

**為什麼 ctrl+click 改的東西不寫回設定檔**：設定檔是專案規定，不該被隨手改一下就污染。想永久改就去改 JSON。

**暫存序列為什麼放在輸出資料夾底下而不是系統 temp**：萬一轉檔失敗，你知道去哪撿那些圖。轉檔成功就自動刪掉（shift+click 可以保留）。
