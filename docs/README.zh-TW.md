<div align="center">

# DLSSG Manager

**為 RTX 20 / 30 系列顯卡解鎖 DLSS 影格生成的一鍵式圖形工具**

[简体中文](../README.md) · **繁體中文** · [English](README.en.md)

[![Release](https://img.shields.io/badge/Release-v1.9.6-5B8CFF)](#下載與安裝)
[![Platform](https://img.shields.io/badge/Platform-Windows%20x64-333D52)](#下載與安裝)
[![Upstream](https://img.shields.io/badge/Upstream-dlssg__for__sm86-9B7BFF)](#致謝與出處)

</div>

---

## 致謝與出處

> **本專案的核心能力完全來自上游專案 [dlssg_for_sm86](https://github.com/sdli1995/dlssg_for_sm86)，由 [sdli1995](https://github.com/sdli1995) 開發維護。**
>
> 正是上游作者對 DLSSG Native（`version.dll` 代理 + SM86 / SM75 核心路由）的逆向與封裝，
> 才讓 RTX 20 / 30 系列使用者用上 DLSS 影格生成。本工具只是站在這個肩膀上，
> 把「找遊戲目錄、挑入口 DLL、寫設定、管備份」這些繁瑣步驟做成了圖形介面。
>
> **向原作者致上敬意與感謝。** 上游二進位檔（payload/ 下的 DLL）隨本工具原樣散布，
> 未做任何修改，版權歸原作者所有；若上游專案對你有幫助，請先去給上游一個 Star。

### 關於更新

本工具**會跟隨上游專案 [dlssg_for_sm86](https://github.com/sdli1995/dlssg_for_sm86) 的更新**：

- 上游發布新版本（新的推論核心、相容性修正等）時，
  本儲存庫會同步更新 `payload/` 內的執行庫檔案並發布新的 Release；
- 介面與辨識邏輯也會跟隨上游的能力邊界調整（例如新顯卡支援、生成影格上限變化、
  一致性檔位這類語意變化）；
- 因此**建議使用最新 Release**，而不是停留在舊版本 —— 上游的相容性修正
  往往直接決定某些遊戲能不能正常開起來。

如果你發現上游已更新而本工具尚未跟進，歡迎提 issue 提醒。

各版本變更彙總見 [CHANGELOG.md](../CHANGELOG.md)。

DLSS 與 DLSS Frame Generation 是 NVIDIA Corporation 的商標與專有技術。上游 0.4.1 執行包按官方發布原樣散布，
包含 NVIDIA 與 Intel 第三方二進位檔；授權與來源見 `payload/THIRD_PARTY_NOTICES.txt`，本工具不修改這些檔案。

### 為什麼做這個工具

和我一起打遊戲的好友裡，好幾個還在用 RTX 30 系列、20 系列顯卡。他們看到別人開影格生成，
抱怨自己的卡「沒有生成」。我把原作者的專案分享給他們——GitHub 勉強連得上，可打開
之後盯著頁面看了半天，還是不知道從哪裡下手。於是我把以前的舊電腦翻出來，做了這個
圖形工具：現在他們點兩下按鈕，影格生成就開起來了。

這個工具是寫給他們的，也寫給每一個和當時的他們一樣的你。

---

## 介面預覽

<div align="center">

<img src="screenshot.png" width="880" alt="DLSSG Manager 主介面">

<sub>主介面 —— 左側遊戲清單，右側辨識結果與影格生成設定</sub>

</div>

<details>
<summary><b>更多截圖</b>（一致性檔位 / 英文介面 / 窄視窗）</summary>

<br>

**一致性檔位（上游 0.3.2 新增）** —— 可選 0–3 四檔：

<div align="center">
<img src="screenshot_tier.png" width="620" alt="一致性檔位 0–3 四檔">
</div>

**English**：

<div align="center">
<img src="screenshot_en.png" width="820" alt="English UI">
</div>

**窄視窗（820×900）** —— 設定列自動換行，內容可捲動，不裁切不重疊：

<div align="center">
<img src="screenshot_narrow.png" width="620" alt="窄視窗版面">
</div>

</details>

---

## 這是什麼

DLSSG Manager 自動掃描本機已安裝的 D3D12 遊戲，定位真正的算繪 EXE，
一鍵部署 / 一鍵還原上游 DLSSG 代理與設定，讓 RTX 20（SM75）/ RTX 30（SM86）
顯卡在支援 DLSS 的遊戲中開啟**影格生成**。

### 功能一覽

- **自動辨識遊戲**：Steam / Epic / GOG / Ubisoft 平台庫 + 按磁碟機代號深度掃描 + 手動新增目錄，
  自動穿透啟動器定位真正的算繪 EXE，並辨識 Unreal / Unity 引擎
- **啟動與掃描更順暢**：啟動動畫沿用靜態背景，顯卡偵測與執行包校驗在背景完成；遊戲目錄最多 4 路並行分析，結果順序保持一致
- **一鍵啟用 / 一鍵還原**：入口 DLL 自動避讓（version → winmm → dbghelp → dinput8），
  絕不覆蓋他人檔案；部署帶 SHA256 校驗與自動備份，還原後恢復原狀
- **一致性檔位（0–3）**：直接決定「生成畫面能偏離官方執行庫多遠」——
  `0` 原廠核心（最保守）、`1` 全部逐位一致的加速（預設，**畫面與官方完全相同**）、
  `2` 再加上有損影像核心、`3` 全部有損加速（最快）
- **兩種插幀引擎**：DLSS-G 為預設；可選 XeSS-FG 多影格生成（2X–4X）
- **DLSS 超解析度選項**：M/L INT8 或 FP16 核心，預設關閉，RTX 20 / 30 系列可用
- **可解釋的設定項**：滑鼠游標停留可查看 DLSS-G A/B/C 預設及每個 DLSS 超解析度模式的說明；掃描誤報可從卡片右鍵移除並忽略（不會刪除遊戲檔案）
- **配套執行庫**：使用上游 0.4.1 的 310.9.16；DLSS-G 最高 6X，XeSS-FG 最高 4X，實際倍率還受遊戲本身限制
- **相容執行庫回退**：新執行庫讓遊戲崩潰時，可切到 310.9 或 310.1 相容執行庫（上游 0.3.5）重新部署；介面會自動收起 0.4.x 專屬選項，並跟著調整倍率 / 檔位上限
- **解析度感知**：讀取 UE / Unity 設定估算目前解析度，給出顯示記憶體增量預算
- **防作弊提示**：偵測到防作弊系統時僅作提示，不影響任何功能使用
- **系統準備**：硬體加速 GPU 排程（HAGS）偵測 + 一鍵開關 + 跳轉系統設定，影格時間更穩
- **入口分層比照上游**：工具類代理優先（`version` → `winmm` → `dbghelp` → `dinput8`，自動選擇只走這組）；
  `dxgi` / `d3d12` 屬 D3D12 算繪熱路徑、載入順序敏感，列為高風險並由你手動指定，**兩者互斥**（部署時強制校驗）
- **顯卡名稱偽裝**：把顯卡名稱偽裝成 RTX 40 / 50 系列（50 / 60 / 70 / 80 / 90 及 Ti 檔位），
  繞過部分遊戲按型號判斷的限制；支援自訂型號，隨時一鍵還原。
  寫入系統「裝置執行個體」名稱（DXGI / WMI 讀取處）並提供**一鍵重啟顯卡**使變更立即生效
- **更新檢查**：啟動時靜默檢查新版本（6 小時內只查一次），發現新版本時標題列出現可點擊徽章；
  也可隨時點頁尾「檢查更新」。**只讀公開 API，不上傳任何本機資料**
- **多語言**：簡體中文 / 繁體中文 / English，跟隨系統自動選擇；
  社群可在 `lang/` 目錄新增語言檔案，無需重新打包
- **精緻介面**：無邊框圓角暗色 UI、KANNI 載入動畫、macOS 風格三色視窗按鈕、像素級文字省略

---

## 下載與安裝

前往 [**Releases**](../../releases) 頁面下載對應版本（目前 **v1.9.6**）：

| 版本 | 檔案 | 適合對象 |
|---|---|---|
| **免安裝可攜版** | `DLSSG_Manager_1.9.6_portable_x64.zip` | 想解壓即用、綠色不寫登錄檔 |
| **標準安裝版** | `DLSSG_Manager_1.9.6_setup_x64.exe` | 想要安裝精靈、開始功能表/桌面捷徑與完整解除安裝 |

**可攜版**：解壓到任意目錄，雙擊 `DLSSG Manager.exe` 即可。
**安裝版**：雙擊 setup，依精靈選擇目錄安裝；解除安裝請到「設定 → 應用程式 → 已安裝的應用程式」或
開始功能表中的 Uninstall，會一併清理捷徑與登錄檔項目。

> 兩個版本功能完全一致，都自帶 `payload/` 執行庫與多語言檔案，**不需要安裝
> Python / CUDA / 任何執行環境**（首次啟動 2–4 秒解壓縮屬正常現象）。

---

## 使用說明

1. 啟動後軟體自動掃描本機遊戲（也可點「深度掃描」按磁碟機代號全盤反查，或「手動新增遊戲目錄…」）；
2. 左側選取遊戲，右側確認辨識結果（算繪行程、解析度、防作弊提示、部署狀態）；
3. 選擇插幀引擎、倍率與一致性檔位；DLSS-G 預設和超解析度模式可依需求調整，預設超解析度關閉；
4. 點擊 **「一鍵啟用插幀」**，完全退出遊戲後重新啟動；
5. 在遊戲畫面設定中開啟影格生成並選擇倍率（DLSS-G 最高 6X，XeSS-FG 最高 4X）；
6. 想還原時回到本工具點 **「一鍵還原」**，遊戲目錄會清理乾淨。

更多細節（顯示記憶體預算、INI 參數、排查方法、能力邊界）見 [docs/使用说明.txt](使用说明.txt)（簡體中文）。

### 系統需求

| 項目 | 要求 |
|---|---|
| 系統 | Windows 10 2004+（build 19041）/ Windows 11，x64 |
| 顯卡 | NVIDIA RTX 20 / 30 系列（SM75 / SM86） |
| 驅動 | NVIDIA R580 或更新版本（上游 0.4.x 的硬性要求） |
| 遊戲 | D3D12 且內建 DLSS 執行庫（工具會自動判斷並提示） |

---

## 多語言

介面語言在**標題列右上角下拉選單**切換（重新啟動程式生效），首次啟動跟隨系統語言。
新增語言：在程式目錄建立 `lang/<語言代碼>.json`（UTF-8，鍵為簡體中文原文，值為譯文，
另加 `"_meta": {"name": "語言原生名"}`），參照內附的 `lang/en_US.json`，重新啟動即可。
命令列也可用 `--lang en_US` 暫時指定。

---

## 從原始碼建置

```bat
git clone https://github.com/kanniganfan/dlssg-manager.git
cd dlssg-manager
python scripts\import_upstream_release.py path\to\dlssg-release-0.4.1-x64.zip
scripts\build_windows.bat
python scripts\build_release.py --portable-only
```

先用 `scripts/import_upstream_release.py` 校驗官方 0.4.1 發布包 SHA-256 並匯入 `payload/`，
再建置程式與發行包。發布物包含完整執行包、來源授權和第三方聲明。

目錄結構：

```
src/       Python 原始碼（core 邏輯核心 / ui 介面 / i18n 引擎 / main 進入點）
lang/      介面語言檔案（JSON，可直接編輯或新增語言）
assets/    圖示資源
docs/      使用說明與介面截圖
scripts/   建置、校驗與維護腳本
```

`scripts/` 裡的自檢腳本（提交前會跑）：

| 腳本 | 作用 |
|---|---|
| `check_tuple_arity.py` | 校驗 `ENTRIES` / `RUNTIMES` 等常數表的元組長度一致 |
| `check_i18n_keys.py` | 比對 `src/` 裡 `tr()` 用到的鍵與字典，列出缺少 / 多餘 |
| `check_upstream_sync.py` | 檢查上游是否有新版本，並用 git blob SHA-1 驗證本機 payload 與上游 HEAD 是否逐位元組一致（結束碼 0=已同步 / 1=需同步） |
| `smoke_ui.py` | 離屏 UI 冒煙：檔位連動、`FlowRow` 換行、toast 定位、按鈕不裁字、更新檢查三態 |
| `e2e_deploy.py` | 暫存目錄裡跑 部署 → 讀回 → 還原 閉環 |
| `scan_parallel_check.py` | 暫存合成目錄檢查並行掃描的結果順序、去重和耗時 |
| `build_release.py` | 打包可攜版 zip + NSIS 安裝程式 |

---

## 能力邊界與免責聲明

- 僅支援 **Windows x64 + D3D12** 遊戲；Vulkan 暫不支援
- 影格倍率上限取決於引擎與遊戲：DLSS-G 最高 6X，XeSS-FG 最高 4X，多數遊戲受內建外掛上限約束
- XeSS-FG 和超解析度模式為可選項；效果和效能依遊戲、顯卡及解析度而異，預設使用 DLSS-G 且關閉超解析度
- 上游 0.4.1 的實卡與離線測試範圍見 `payload/README.md`，不同引擎、顯卡與遊戲的結果並不相同
- **防作弊提示**：偵測到防作弊系統時僅作提醒；請自覺只在單機 / 離線 / 實驗室環境使用，
  線上模式的使用由使用者自行判斷與承擔
- **更新檢查**：啟動時靜默檢查本工具是否有新版本（6 小時內只查一次），
  也可隨時點頁尾「檢查更新」；發現新版本時標題列出現可點擊的版本徽章。
  檢查是**唯讀的 GitHub 公開 API 查詢，不上傳任何本機資料**，也不傳送任何識別資訊
- 除上述更新檢查外，本工具不連網、不上傳任何資料，全部操作在本機完成
- 修改遊戲目錄前請確認已了解上述內容，使用本工具產生的一切後果由使用者自行承擔

---

## 聯絡方式

- 電子郵件：[cylqm@qq.com](mailto:cylqm@qq.com)
- 電子郵件：[cao673100060@gmail.com](mailto:cao673100060@gmail.com)

歡迎 issue / PR；語言檔案捐贈（任何語種）尤其歡迎。

---

## License

本專案程式碼以 [MIT License](../LICENSE) 發布。
`payload/` 內的上游執行包按官方發布原樣隨附；各第三方檔案保留其原授權，
詳見 `payload/LICENSE.md` 和 `payload/THIRD_PARTY_NOTICES.txt`。DLSS 技術與商標歸 NVIDIA Corporation 所有。

---

<div align="center">

**Again, all credits to [sdli1995/dlssg_for_sm86](https://github.com/sdli1995/dlssg_for_sm86)**

</div>
