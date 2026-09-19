# Board20 Step5 full-q第二候选v2独立只读封存审计

> 结论：`V2_STOPPED_SELFTEST_FAIL_NO_PILOT`。v2不得进入pilot/full，不改写第一次compact validator的2项FAIL。

## 人话结论

- 候选自身preflight：45/45 PASS，说明文件、矩阵、路线和算法选择封签成功。
- 候选自身synthetic selftest：57 PASS / 6 FAIL，所以科学计算必须在pilot之前停止。
- `outputs/step5_fullq_candidate/pilot` 和 `full` 均不存在，没有候选网格可被误认为通过。
- 此审计只封存v2失败现场；未来v3必须使用新合同、新脚本哈希和新验收身份。

## 六个原门槛失败

| 候选selftest check_id | 实际值/失败码 |
|---|---:|
| n5.GUYAN_DIV1_H_LEFT.1.2.point_status | GATED_PHYSICAL_POLYNOMIAL_RESIDUAL;GATED_PHYSICAL_LAURENT_RESIDUAL |
| n5.GUYAN_DIV1_H_LEFT.1.2.poly_residual | 1.736594338981195e-08 |
| n5.GUYAN_DIV1_H_LEFT.1.2.laurent_residual | 1.7363850133874677e-08 |
| n5.DIV2_H_LEFT_FEEDBACK_OUTSIDE.2.1.point_status | GATED_PHYSICAL_POLYNOMIAL_RESIDUAL;GATED_PHYSICAL_LAURENT_RESIDUAL |
| n5.DIV2_H_LEFT_FEEDBACK_OUTSIDE.2.1.poly_residual | 3.934582572464684e-06 |
| n5.DIV2_H_LEFT_FEEDBACK_OUTSIDE.2.1.laurent_residual | 3.934474327859885e-06 |

## 证据保护

- v1草稿、v2修订记录、v2合同/脚本/输入封签哈希均与预登记值相同。
- 第一次compact全网格验收仍是 `S5-POST-0095` 和 `S5-POST-0108` 两项FAIL。
- 条件性诊断仍是 `DIAGNOSTIC_ONLY_VALIDATOR_FAIL_UNCHANGED`。
- 审计前后所有受保护工件SHA-256完全不变。
