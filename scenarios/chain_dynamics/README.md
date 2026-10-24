# MATLAB 链式动力学复杂验收

该场景研究两端固定的质量-弹簧-阻尼多自由度链，使用纯 base MATLAB 的 `eig`、`ode45`、`odeset`、`save` 和 `jsonencode`。适配器只接收参数数据，不接收自由 MATLAB 代码；`script`/`analysis` 旧编译器不会被当作本操作的验收。

## 科学任务

| 项 | 内容 |
|---|---|
| 系统 | `M x'' + C x' + K x = f(t)`，`M=diag(m)`，`K` 为三对角固定端链，`C = alpha*M + beta*K` |
| 模态 | 广义特征值 `eig(K,M)`、质量正交性 `V'MV=I`、特征残差；均匀链与解析式 `omega_r = 2 sqrt(k/m) sin(r pi/(2(N+1)))` 比较 |
| 阻尼 | 一阶状态矩阵特征值，比较独立 SciPy 结果中的阻尼固有频率与阻尼比 |
| 瞬态 | 多节点、多频正弦外力，`ode45` 紧容差积分，输出 1001 个以上样本 |
| 能量 | 动能+势能、外力功 `∫f·v`、阻尼耗散 `∫v'Cv`，检查 `E(t)-E(0)-W+D≈0` |
| 残差 | 二阶中心/单边差分求加速度，检查 `M a + C v + K x - f` 的相对残差 |

三个冻结作业：均匀 `N=12`（有解析频率）、非均匀 `N=48`、高刚度 `N=96`；样本数 1501/2001，两个全新目录各跑一遍。

## 复现步骤

```powershell
# 1. 先冻结 SciPy 期望与容差（不运行 MATLAB）
python scenarios/chain_dynamics/oracle.py scenarios/chain_dynamics/jobs/chain-uniform-n12.json <expectations>/chain-uniform-n12
python scenarios/chain_dynamics/oracle.py scenarios/chain_dynamics/jobs/chain-graded-n48.json   <expectations>/chain-graded-n48
python scenarios/chain_dynamics/oracle.py scenarios/chain_dynamics/jobs/chain-highstiff-n96.json <expectations>/chain-highstiff-n96

# 2. 真实 MATLAB 双运行 + 独立比较（未安装时写 blocked，退出 2）
python scenarios/chain_dynamics/run_study.py --matlab "<MATLAB_HOME>/bin/matlab.exe"

# 3. 负例与恢复（编译期负例不需要 MATLAB；原生失败/缺产物/超时需已安装）
python scenarios/chain_dynamics/negative_controls.py --matlab "<MATLAB_HOME>/bin/matlab.exe" --expectations-root <expectations>

# 4. 单独复核某次运行
python scenarios/chain_dynamics/compare.py --run <run-dir> --expectations <expectations>/<job-id> --job scenarios/chain_dynamics/jobs/<job>.json
```

`run_study.py` 默认把证据写到 **当前工作目录** 的 `runs/study` 与 `oracles/expectations`，可用 `--run-root`/`--expectations-root` 覆盖；它不会从包安装位置推断研究目录。缺少 MATLAB 时只生成 `study-report.json` 的 `blocked` 记录，不生成任何成功产物。`negative_controls.py` 同样默认使用 cwd，并在第一项负例之前冻结恢复用期望；已有期望不会被改写。

## 实现教训（本轮真实运行）

- `version('-release')` 返回 `2026a`（没有 `R` 前缀），`R2026a` 只出现在 `version` 字符串里。验收按 `2026a` 检查，并用 `version` 包含 `(R2026a)` 交叉核验。
- `save(...,'-v7')` 写出的 MAT 文件头是 `MATLAB 5.0 MAT-file`（v7 沿用 5.0 头），不是 `MATLAB 7.0`。验收检查 5.0 头，并用 `scipy.io.loadmat` 读取变量与结构。
- “预期 blocked”的模拟缺运行时控制**执行且符合预期**时算通过，不能让总体变成 blocked；只有必需的 native 控制未执行才是 blocked。
- 打包后的 runner 不得从 `__file__` 推断研究目录；输出默认是 cwd，期望目录显式传入，安装目录只用于读脚本与作业模板。


## 验收含义

| 检查 | 独立依据 |
|---|---|
| 模态频率 | 均匀链解析式（相对 `1e-10`）；所有算例对照 `scipy.linalg.eigh`（相对 `1e-8`） |
| 质量正交性 / 特征残差 | 由 MATLAB 输出重算，阈值 `1e-9`；同时要求 `mode_residual` 与 `results.json` 一致 |
| 阻尼模态 | 独立 SciPy 一阶状态矩阵特征值；按阻尼固有频率排序后比较（相对 `1e-6`，阻尼比绝对 `1e-7`） |
| 瞬态 | 同一外力下 DOP853 紧容差解；位移/速度相对 Frobenius 误差 `1e-4` |
| 能量 | MATLAB 与 SciPy 的总能量轨迹 `1e-4`；能量平衡阈值由 SciPy 梯形积分误差地板乘 10 后冻结，且不低于 `1e-3` |
| 动态残差 | 同一二阶差分口径；阈值同样由 oracle 地板冻结，且不低于 `1e-3` |
| 原生 MAT | v7 头、`scipy.io.loadmat` 读取、变量形状、`M/K/C` 与作业参数、MAT 与 CSV 一致性（`1e-12`） |
| 形状/有限性 | CSV 列名与行数精确匹配，任何 NaN/Inf、截断或重复列直接失败 |
| 重复运行 | 两个新目录逐元素差 `1e-10`，并记录各自输入哈希 |

`results.json` 内部的 `checks` 只是自检；独立验收以 `compare.py` 的 `comparison.json` 为准。MATLAB 身份要求 `release == R2026a`、`version('-release')`、`matlabroot` 与 `batchStartupOptionUsed` 均由 MATLAB 自己写出；不读取任何许可证内容。

## 负例

- 编译期：零/负质量、负刚度、维度不匹配、非有限值、Rayleigh 阻尼全零、注入 `script` 自由代码（6 类真实拒绝）。
- 运行时：缺运行时（`strict_executables` 指向不存在路径）、生成的 MATLAB 程序主动 `error`、产物缺失、1 秒超时；随后用合法作业恢复并通过 oracle。
- 缺 MATLAB 时，需要 MATLAB 的三项运行时负例记为 `blocked`，不会写成通过。
