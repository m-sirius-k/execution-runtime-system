# Execution Runtime Governance System v1.0 — 運用手順書

対象: `v1.0-runtime-governance-final`

## 1. 入力の作り方（Task Specの形式）

`workflow_dispatch`を起動する際、以下3つを入力する。

- `task_intent`：何をするかを表す自然文または短い識別文字列。`MoCKA`という語や`decision`/`rule`/`policy`/`judgment_logic`等の語を含めると拒否される。
- `task_params`：JSON文字列（例：`{"name":"world"}`）。同様にキー名に判断ロジックを示す語を含めると拒否される。
- `human_identity`：実行を依頼する人間の識別子。

## 2. 承認の意味（Approval Gateの扱い）

`approval`ジョブはGitHub Environment `production`のRequired reviewerに紐づいている。**ここでの承認が、システム全体における唯一の人間判断点。** 承認するとは「この`task_intent`と`task_params`の内容を読み、その通り実行してよいと判断したこと」を意味する。承認画面に進む前に`Log Task Intent`ステップの出力を必ず確認すること。

## 3. 実行の流れ（run_coreの役割）

承認後、`run_core`ステップが`runtime/cli.py`を実行する。これはTask Spec→Approval Gate（内部的なtoken発行）→Execution Coreの1回限りの実行であり、ループしない。同じtokenは2回使えない。

## 4. divergenceの読み方（OK / MEDIUM / HIGH / CRITICAL）

実行結果が「意図通りだったか」を示す指標。

- `OK`：intentとexecutionが一致。
- `MEDIUM`：実行は意図通りだが、warningsが発生した。
- `HIGH`：実行結果の状態（final_state）が期待（expected_state）と異なる。
- `CRITICAL`：実行されたタスク自体がintentと異なる。

## 5. CRITICAL時の挙動（Stopの意味だけ）

`divergence_status`が`CRITICAL`の場合、`Stop on Critical Divergence`ステップがジョブを失敗させて停止する。これは「これ以上先に進めない」という意味であり、`Write Job Summary`と`Create Audit Issue`は`always`指定により、停止した場合でも実行される。

## 6. Audit Issueの読み方（記録の意味だけ）

各実行ごとに`Deployment Audit - Run <run_id>`というIssueが必ず1件作成される（成功・失敗・CRITICAL停止を問わず）。Issue本文には実行されたintent/params、承認者、divergence_status、checked_atが記録される。これは「何が承認され、何が起きたか」の唯一の外部証跡であり、後から検索・参照するための記録。
