# 统计桥接复杂验收

该场景使用完全合成的三组纵向干预研究：144 名受试者、4 次随访、576 行，包含随机截距、基线分数和年龄协变量、组别与时间交互，以及预先设定的随访缺失。种子为 `20261024`，本机固定生成 535 个完整观测和 41 个结局缺失观测。完整病例分析会如实记录排除数，不声称完成缺失值插补。

## 可复现步骤

1. `python scenarios/statistics/prepare.py ABSOLUTE_WORKSPACE` 生成 CSV、独立 QR OLS 参照值和全部引擎作业。
2. 通过插件编译、运行 `jobs.json` 内对应的作业，每项放在 `ABSOLUTE_WORKSPACE/JOB_ID`。没有安装或没有许可证的引擎只生成原生源代码，不能记为通过。
3. `python scenarios/statistics/validate.py ABSOLUTE_WORKSPACE` 核对已经执行的数字产物。`execution_records.json` 和插件运行结果共同决定哪些引擎确实执行；验证器只评价实际存在的结果，不能用它的汇总状态推断未执行的引擎通过。

## 验收含义

| 检查 | 独立参照与要求 |
|---|---|
| Python / R / jmv / Octave / Julia / SPSS OLS | 同一 8 列设计矩阵（含截距）；纯标准库 QR 分解参照，系数和标准误绝对误差小于 `1e-7`，R² 和残差标准差误差小于 `1e-9` |
| 缺失数据 | 三者都必须使用 535 个完整观测，排除 41 行并留下审计字段 |
| R 混合模型 | `nlme::lme` 随机截距模型；用返回的方差分量独立重建每名受试者协方差块，再求 GLS 固定效应，误差小于 `1e-7` |
| 方差合理性 | 随机截距方差、残差方差必须为正，满足预定合成数据恢复范围；这不是对方差估计器的独立 ML/REML 实现 |
| 多重比较 | 4 个时点 × 3 对组别，共 12 个比较统一作为同一家族做 Holm 校正；独立重算校正值 |
| Bootstrap | 按受试者整簇抽样，保留每人的所有已观察随访；200 次，重复设置同一随机种子后数组逐项相同 |
| SPSS 探测回归测试 | 测试替身验证 worker 确实调用 `StartSPSS`、`Submit` 和数据集哨兵；未授权异常不会写成功产物或成功标记。此项不是本机真实 SPSS 引擎验收 |

OLS 的普通标准误只适用于独立残差假设。在该纵向研究中，OLS 用于跨引擎数值核对，主要研究推断使用保留受试者相关性的混合模型和簇 bootstrap。一个合成研究通过，不能代替所有模型、所有输入、所有软件版本的验收。

## 本机验收记录（2026-10-24）

- R `4.6.1`，jmv `2.8.0`，nlme `3.1.169`，emmeans `2.0.4`。
- Python / R / jmv / Octave / Julia / SPSS 真执行成功，所有产物及成功标记齐全。
- OLS 最大系数绝对误差：Python `1.5854e-13`；R / jmv `2.1538e-14`。
- 新装 GNU Octave `11.3.0` 最大系数误差 `4.5741e-14`；Julia `1.13.2` 最大系数误差 `2.3537e-14`；标准误、排除行数、R² 和残差标准差也全部通过同一参照核对。
- IBM SPSS Statistics `27` 完整描述统计、OLS、OMS 真执行成功；全精度 OXML 数值属性转成统一 CSV / JSON，最大系数误差 `3.8369e-13`，标准误、R²、残差标准差与完整病例审计均通过。
- 混合模型固定效应与独立 GLS 最大误差 `1.0755e-9`；12 项 Holm 校正最大误差 `9.9920e-16`。
- 随机截距方差 `12.243973`，残差方差 `4.030814`，ICC `0.752328`。
- 固定种子的 200 次簇 bootstrap 逐项复现。

jamovi 在此指 `jmv` R 分析后端；没有控制或验证 jamovi GUI 活会话、界面操作、`.omv` 往返。RStudio 同样只是已安装的 IDE，该插件使用独立 Rscript 进程。

SPSS 使用自带 Python 驱动独立引擎；探测要求实际成功启动、提交哨兵数据、确认两个 case，并写成功 JSON 和唯一 stdout 标记。进程退出码为 0 本身不表示授权或引擎可用。SPSS OLS 的原生数值输出采用 OMS OXML，已真实运行并从 `number` 属性核对全部回归结果；不会使用显示时只保留三位小数的 `text` 值作为数值参照。

本机默认沙箱会阻止 SPSS 本地进程间通信，导致 `StartSPSS` 等待；在自动审批允许的单项提升执行中，真实探测和研究分析均可通过。这一沙箱限制不能解释为“未授权”。一次默认沙箱超时留下了本次运行的孤儿 `StartXD.exe`，经父 PID 和创建时间核对后只清理了该进程，未操作用户其他 SPSS 会话。主线宿主已改用 Windows Job Object，在启动子进程前取得归属并在超时关闭所属进程树；worker 另有当前用户及安装目录专属的 Windows 命名互斥锁，默认有限等待 10 秒，忙时输出 `RB_BLOCKED` 并退出。`lock_wait_s` 允许 0 到 30 秒。不得按进程名批量结束科研软件。

Stata、MATLAB、SAS 的模板包含数值导入和回归源代码，但本机未完成其真实引擎验收。Stata 模板已静态修正 JSON 引号闭合、保留变量名大小写，并添加秩和自由度检查；SAS 使用 ODS 参数估计数据集生成统一 CSV / JSON，在错误状态或参数表缺失时中止，不再单凭一个尾部成功文件误判。以上静态修正仍不等于对应商业引擎验收。Octave 和 Julia 已在隔离工具目录安装并通过同一 OLS 场景。两者无第三方依赖的 CSV 模板仅支持本场景的简单 CSV，会明确拒绝引号字段或行列数不一致，不会把错位数据继续当成有效模型；复杂 CSV 应通过 `script` 操作使用 CSV.jl 或适用的 Octave CSV 解析包。

新装便携软件均来自官方页面，未修改 PATH、注册表或原有解释器。Julia ZIP 的 SHA256 与官方清单匹配；Octave 7z 的官方分离签名使用 GNU 官方 keyring 验证成功，指纹为 `DBD9C84E39FE1AAE99F04446B05F05B75D36644B`。原始下载、校验清单、签名和安装收据由安装缓存保留；插件分发包应只包含安装脚本与收据，避免把约 775 MB 的软件归档混入插件。

## 官方接口依据

- [jamovi 官方：jmv 是其核心统计分析的 R 包](https://www.jamovi.org/jmv.html)
- [jamovi 线性回归参数与结果表接口](https://jamovi.readthedocs.io/da/latest/jmv/jmv_linReg/)
- [IBM：从外部 Python 进程驱动 SPSS](https://www.ibm.com/docs/en/spss-statistics/30.0.0?topic=programs-running-spss-statistics-from-external-python-process)
- [IBM：GetLastErrorLevel 与 GetLastErrorMessage](https://www.ibm.com/docs/en/spss-statistics/32.0.0?topic=classes-spssgetlasterrorlevel-spssgetlasterrormessage-functions-python)

旧桥接器的 `check` 分支只递归切换 Python，没有调用 `cmd_check()`，因此会误报成功。本插件不复用那个入口，也不修改旧文件。SPSS 许可证、学校认证与授权服务器配置由合法授权流程处理，桥接器不修改许可证文件。
