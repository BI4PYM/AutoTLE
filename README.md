# AutoTLE V2

使用Vibe Coding

自动化更新业余卫星星历，兼容传统 TLE，并支持 TLE 编号耗尽后的 OMM 多格式输出。

自动化更新HAM常用的卫星TLE星历文件

帖子：https://www.hellocq.net/forum/read.php?tid=370636 https://forum.hamcq.cn/d/3323

AutoTLE五周年，AutoTLE正式更新为AutoTLE V2

添加Norad ID>10000卫星的支持,支持Celestrak新接口,映射到70000~89999,兼容Orbitron

添加OMM JSON到TLE格式转换,支持多卫星列表输出

新增 静安梦想 八一04 两颗卫星

欢迎推荐TLE文件里当前没有的，常用或者最新的卫星以便加入更新列表！

现有卫星：

ISS,SO-50,AO-91,PO-101,RS-44,

AO-7,LILACSAT-2,FO-29,TIANQIN 1 (CAS-6),CSS,

JO-97,METEOR-M2 3,METEOR-M2 4,XW-3 (CAS-9),MT-CUBE-2,

ES'HAIL 2,GK-2A,SONATE-2,ASRTU-1 (AO-123),MESAT1,

RS95S,TEVEL2-9,TEVEL2-8,TEVEL2-7,TEVEL2-6,

TEVEL2-5,TEVEL2-4,TEVEL2-3,TEVEL2-2,TEVEL2-1,

GEMINI-POLLUX,HADES-SA,BY70-4,JAMX01

服务器星历更新频率：由于celestrak每两小时检测一次，AutoTLE也将两小时检测一次，保证TLE源数据有变动就会自动更新

食用方法：把追星软件（如Orbitrn，“追星”等）的TLE来源设置为

http://raw.githubusercontent.com/BI4PYM/AutoTLE/refs/heads/master/AutoTLE.txt

http://autotle.bi4pym.cn/AutoTLE.txt

如无法更新，可自行寻找github镜像源使用

注意！有些软件（如Orbitron）不支持HTTPS

最新卫星列表及状态请在`logs.txt` `satellites_state.md`中查询

## 功能

- 从 CelesTrak 获取 GP/OMM：默认顺序 `JSON -> KVN -> CSV -> XML -> TLE`。
- CelesTrak 无数据时回退 SatNOGS：`GET /api/tle/?format=json&norad_cat_id=...`，也支持 `sat_id`。
- CelesTrak 与 SatNOGS 都失败时，优先级回退 `localTLE.txt`、`localJSON.json`、已有 `satellites.pkl`。
- 星历统一保存为 OMM 字典列表，pickle 文件为 `./satellites.pkl`。
- 按卫星 `EPOCH` 判断新旧，只有新数据才替换已有星历。
- 每个 `./satellitelists/*.json` 生成同名输出到 `./satellites/`。
- 每个列表更新后都会额外生成同名 TLE `.txt` 到项目根目录 `./`，即使列表未声明 TLE。
- 每次运行覆盖写入 `./logs.txt`，记录每个卫星的编号、名称、来源和更新状态。

## 输出格式

列表文件中的 `formats` 支持：

`TLE`、`3LE`、`2LE`、`JSON`、`JSON-PRETTY`、`KVN`、`CSV`、`XML`

文件映射：

| 格式 | 输出后缀 |
|---|---|
| `TLE` / `3LE` | `.txt` |
| `2LE` | `.2le.txt` |
| `JSON` / `JSON-PRETTY` | `.json` |
| `KVN` | `.kvn` |
| `CSV` | `.csv` |
| `XML` | `.xml` |

## 卫星列表格式

推荐格式：

```json
{
  "formats": ["TLE", "JSON", "KVN", "CSV", "XML"],
  "satellites": [
    {"id": "25544", "name": "ISS(ZARYA)", "query": "CATNR"},
    {"id": "100469", "name": "FUTURE-1", "query": "CATNR"}
  ]
}
```

兼容旧格式：

```json
[
  ["25544", "ISS(ZARYA)", "CATNR"],
  ["100469", "FUTURE-1", "CATNR", ["TLE", "JSON"]]
]
```

`query` 支持 `CATNR`、`NAME`、`INTDES`、`GROUP`、`SPECIAL`、`SATID`、`SAT_ID`。旧列表未声明格式时默认只输出 `TLE`，以保证原行为不变。

## 多列表

`./satellitelists/` 下可放任意数量 JSON 文件。每个文件独立生成：

- `./satellites/<列表名>.<格式后缀>`
- `./<列表名>.txt`，作为根目录 TLE 兼容文件

例如 `AutoTLE.json` 会生成 `./AutoTLE.txt`，不会再由其他列表额外写同名旧文件。

同一次运行中，同一颗卫星只会抓取一次。后续列表会复用本次运行已经获取到的记录，不再重复访问 CelesTrak、SatNOGS 或本地文件源。

## 本地星历源

- `./localTLE.txt`：本地 TLE/3LE/2LE 文本。
- `./localJSON.json`：本地 OMM JSON。
- 回退优先级：`localtle` 高于 `localjson`。localTLE 有匹配记录时不再尝试 localJSON。
- 完整来源顺序：`celestrak > satnogs > localtle > localjson`。

## 日志与状态

默认运行时，控制台会按卫星逐条打印查询和结果；使用 `--quiet` 时只打印最终汇总。

每次执行 `python main.py` 都会覆盖写入：

- `./logs.txt`：本次运行日志。包含运行时间，以及每个卫星的卫星编号、名称、获取来源、更新状态。
- `./satellites_state.md`：Markdown 缓存状态表，按 `satellites.pkl` 中星历列表的插入顺序输出。

- `logs.txt` 使用 GBK，方便 Windows 中文环境直接查看。
- 其他文件统一使用 UTF-8，包括 `satellites_state.md`、JSON、KVN、CSV、XML、TLE 和 pickle。

`satellites_state.md` 表格列：

| 卫星编号 | 卫星名称 | 星历来源 | 更新时间 | 定轨时间 (EPOCH) | 上一次更新状态 | 这一次更新状态 |
|---|---|---|---|---|---|---|

其中：

- `更新时间`：本地缓存被新增或替换的时间。
- `定轨时间 (EPOCH)`：星历数据自带的轨道历元时间。
- 判断两份轨道数据哪个更新，只比较 `EPOCH`，不比较 `更新时间`。
- JSON、KVN、CSV、XML 和 TLE 转换都会保留并转换 `EPOCH`。

状态包括：`成功新增`、`成功更新`、`星历源与缓存一致`、`星历源比缓存更旧`、`失败`、`失败（使用缓存）`、`未处理`。

## 删除缓存记录

使用 `--delete-id` 删除 `satellites.pkl` 中的星历记录，支持：

- NORAD 编号
- TLE 中实际使用的编号或别名
- INTDES

示例：

```bash
python main.py --delete-id 25544
python main.py --delete-id TLE:70000
python main.py --delete-id INTDES:2020-025
python main.py --delete-id 25544 --delete-id INTDES:2020-025
```

删除时同步清理 `aliases`、`sources`、`status`、`timestamps`，并覆盖更新 `logs.txt` 和 `satellites_state.md`。

注意：`--delete-id` 不修改 `satellitelists/*.json`。如果该卫星仍在任何列表文件中，下一次普通更新会重新加入。

## 大编号映射

- `NORAD_CAT_ID <= 69999`：TLE 中保留原编号。
- `90000 <= NORAD_CAT_ID <= 99999`：视为临时/特殊编号，保留原编号。
- 其他 `NORAD_CAT_ID > 69999`：按 `satellites.pkl` 中的顺序分配稳定别名 `70000..89999`。
- 原始 `NORAD_CAT_ID` 始终保留在 OMM、JSON、KVN、CSV、XML 中；只有 TLE 行使用别名。
- 分配时跳过列表中已有的 5 位真实编号，避免同一列表内编号冲突。
- 新增卫星追加到星历列表末尾；已有卫星在原位置替换，因此别名不会因普通更新而漂移。

## 安装

- Python 3.10 或更高版本。
- 无第三方运行库，不需要安装 `requests`。

## 运行

```bash
python main.py
```

离线仅使用本地文件：

```bash
python main.py --offline --source localtle --source localjson
```

只测试少量卫星：

```bash
python main.py --limit 3
```

指定代理或源顺序：

```bash
python main.py --proxy http://PROXY_HOST:PROXY_PORT --source celestrak --source satnogs --source localtle --source localjson
```

## 命令行参数

| 参数 | 默认值 | 可重复 | 说明 |
|---|---|---|---|
| `--root PATH` | 当前目录 | 否 | 项目根目录，用于定位 `satellitelists/`、`satellites.pkl`、`satellites/` 等文件。 |
| `--list PATH` | 自动发现 | 是 | 指定卫星列表 JSON。可多次传入；未指定时读取 `satellitelists/*.json`，目录为空时回退根目录 `satelist.json`。 |
| `--state PATH` | `ROOT/satellites.pkl` | 否 | 指定 pickle 缓存文件。 |
| `--output-dir PATH` | `ROOT/satellites` | 否 | 指定各卫星列表输出目录。 |
| `--source NAME` | `celestrak,satnogs,localtle,localjson` | 是 | 设置星历源优先级。可选 `celestrak`、`satnogs`、`localtle`、`localjson`、`local`。`local` 为旧兼容项，表示同时使用两个根目录本地文件。 |
| `--celestrak-format FORMAT` | `JSON,KVN,CSV,XML,TLE` | 是 | 设置 CelesTrak 格式尝试顺序，默认优先 OMM JSON。 |
| `--timeout SECONDS` | `20` | 否 | 单次 HTTP 请求超时时间。 |
| `--retries N` | `2` | 否 | HTTP 请求重试次数。 |
| `--proxy URL` | 无 | 否 | 可选的 HTTP/HTTPS 代理，仅设置时才启用。 |
| `--offline` | 关闭 | 否 | 只使用根目录 `localTLE.txt` 和 `localJSON.json`；均无数据时使用已有 pickle 缓存。 |
| `--dry-run` | 关闭 | 否 | 执行获取和合并，但不写 `satellites.pkl`、`satellites/` 输出和根目录 TLE；`logs.txt` 与 `satellites_state.md` 仍会更新。 |
| `--delete-id ID` | 无 | 是 | 删除 pickle 中匹配的缓存记录。支持 NORAD 编号、TLE 编号/别名、`TLE:70000`、`INTDES:2020-025`。 |
| `--limit N` | 不限制 | 否 | 每个卫星列表只处理前 N 条记录，适合测试。 |
| `--quiet` | 关闭 | 否 | 不打印逐颗卫星进度，只输出最终汇总。 |
| `--help` | - | 否 | 显示完整参数帮助。 |

示例：

```bash
python main.py --help
python main.py --limit 3
python main.py --list satellitelists/amateur.json --quiet
python main.py --source celestrak --source satnogs --source localtle --source localjson
python main.py --delete-id 25544
python main.py --delete-id INTDES:2020-025
```

环境变量：

- `AUTOTLE_PROXY`
- `AUTOTLE_SOURCES`，例如 `celestrak,satnogs,localtle,localjson`
- `AUTOTLE_CELESTRAK_FORMATS`，例如 `JSON,KVN,CSV,XML,TLE`
- `AUTOTLE_TIMEOUT`
- `AUTOTLE_RETRIES`
- `AUTOTLE_OFFLINE`
- `AUTOTLE_QUIET`
- `AUTOTLE_STATE`
- `AUTOTLE_OUTPUT_DIR`

## 测试

```bash
python -m unittest discover -s tests -v
```

无第三方 Python 依赖，使用标准库运行。

## 数据格式参考

- CelesTrak GP data formats: <https://celestrak.org/NORAD/documentation/gp-data-formats.php>
- SatNOGS DB API: <https://db.satnogs.org/api/>
- SatNOGS TLE API: <https://db.satnogs.org/api/tle/>

SatNOGS TLE API 当前只支持 `format=json` 和 `format=3le`；`norad_cat_id` 为整数查询参数，`sat_id` 为字符串查询参数。
