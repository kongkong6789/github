import assert from "node:assert/strict";
import { test } from "node:test";

import { extractHumanConfirmationSummary } from "./utils";
import { HITLRequest } from "./types";

test("extracts HITL confirmation summary and available decisions", () => {
  const request: HITLRequest = {
    action_requests: [
      {
        name: "create_purchase_order",
        description: "创建采购单前请人工确认。",
        args: {
          risk_level: "high",
          execution_mode: "approval_request_only",
          data_sources: ["erp", "kingdee_erp"],
          destructive_effects: ["创建采购单会影响 ERP 业务单据。"],
          dry_run_preview:
            "This request only asks for human approval; no external MCP/API write is executed here.",
        },
      },
    ],
    review_configs: [
      {
        action_name: "create_purchase_order",
        allowed_decisions: ["edit", "approve", "reject"],
      },
    ],
    metadata: {
      risk_level: "high",
      execution_mode: "approval_request_only",
      data_sources: ["erp", "kingdee_erp"],
      destructive_effects: ["创建采购单会影响 ERP 业务单据。"],
    },
  };

  assert.deepEqual(extractHumanConfirmationSummary(request), {
    description: "创建采购单前请人工确认。",
    risk_level: "high",
    destructive_effects: ["创建采购单会影响 ERP 业务单据。"],
    data_sources: ["erp", "kingdee_erp"],
    execution_mode: "approval_request_only",
    dry_run_preview:
      "This request only asks for human approval; no external MCP/API write is executed here.",
    decisions: {
      approve: true,
      edit: true,
      reject: true,
    },
  });
});
