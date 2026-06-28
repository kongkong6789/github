import assert from "node:assert/strict";
import {
  mkdir,
  mkdtemp,
  readFile,
  rm,
  symlink,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { test } from "node:test";

import {
  createDraftSkillFromSource,
  deleteSkillRegistration,
  loadGovernanceState,
  restoreSkillSourceFromManagedCopy,
  summarizeGovernanceState,
  upsertMcpToolPolicy,
} from "./governance";

test("governance summary surfaces skill and MCP policy counts", () => {
  const summary = summarizeGovernanceState({
    skillRegistry: {
      skills: {
        strategy: {
          skill_id: "strategy",
          name: "经营策略",
          status: "active",
          version: 2,
          tool_count: 4,
          source_wiki_path: "wiki/strategy/rules.md",
          updated_at: "2026-05-19T10:00:00.000Z",
        },
        draft: {
          skill_id: "draft",
          name: "待审批模板",
          status: "draft",
          version: 0,
          tool_count: 2,
        },
      },
    },
    mcpPolicy: {
      tools: {
        query_erp_live_snapshot: {
          description: "ERP read only",
          read_only: true,
          requires_human_confirmation: false,
          risk_level: "low",
          data_sources: ["erp"],
        },
        create_purchase_order: {
          description: "Create PO",
          read_only: false,
          requires_human_confirmation: true,
          risk_level: "high",
          data_sources: ["erp"],
        },
      },
    },
  });

  assert.equal(summary.skills.skill_count, 2);
  assert.equal(summary.skills.active_count, 1);
  assert.equal(summary.skills.draft_count, 1);
  assert.equal(summary.mcp.tool_count, 2);
  assert.equal(summary.mcp.write_count, 1);
  assert.equal(summary.mcp.confirmation_count, 1);
  assert.equal(summary.policy_validation.status, "warn");
  assert.equal(summary.policy_validation.fail_count, 0);
});

test("governance summary surfaces marketplace templates", () => {
  const summary = summarizeGovernanceState({
    marketplaceTemplates: [
      {
        name: "wps_report_quality",
        display_name: "WPS 报告质量审查",
        version: "0.1.0",
        description: "报告导出前的只读质量检查模板。",
        category: "report_export",
        requires: ["windows_worker"],
        homepage: "https://github.com/yb2460/harness-anything",
        source_url: "https://github.com/yb2460/harness-anything",
        install_cmd: "",
        entry_point: "wps_report_quality --json",
        execution_mode: "cli_json",
        read_only: true,
        requires_human_confirmation: false,
        risk_level: "medium",
        allowed_callers: ["agent_factory_agent"],
        data_sources: ["reports"],
        safety_contract: ["review only"],
      },
    ],
  });

  assert.equal(summary.marketplace.template_count, 1);
  assert.equal(summary.marketplace.confirmation_count, 0);
  assert.equal(summary.marketplace.items[0].name, "wps_report_quality");
  assert.equal(summary.marketplace.items[0].read_only, true);
  assert.equal(summary.marketplace.items[0].requires_human_confirmation, false);
});

test("governance summary normalizes Tool Registry and cross-checks MCP policy", () => {
  const summary = summarizeGovernanceState({
    toolRegistry: {
      schema: "a2a_tool_registry_v2",
      tools: {
        query_erp_live_snapshot: {
          name: "query_erp_live_snapshot",
          handler: "query_erp_live_snapshot",
          description: "ERP read only",
          group: "external_read",
          read_only: true,
          risk_level: "low",
          requires_confirmation: false,
          data_sources: ["ERP_live_readonly"],
          max_result_size: 50000,
          availability_check: "runtime_catalog",
          owner_module: "connector_live_tools",
          visible_agents: ["data_agent", "decision_agent"],
        },
        sync_connector_dataset: {
          name: "sync_connector_dataset",
          handler: "sync_connector_dataset",
          description: "Local snapshot write",
          group: "write_local_state",
          read_only: false,
          risk_level: "high",
          requires_confirmation: true,
          data_sources: ["ERP_live_readonly", "DuckDB"],
          max_result_size: 20000,
          availability_check: "runtime_catalog",
          owner_module: "connector_live_tools",
          visible_agents: ["auto_workflow_agent"],
        },
      },
    },
    mcpPolicy: {
      tools: {
        query_erp_live_snapshot: {
          description: "ERP read only",
          read_only: true,
          requires_human_confirmation: false,
          risk_level: "low",
          data_sources: ["ERP_live_readonly"],
        },
        sync_connector_dataset: {
          description: "Snapshot write",
          read_only: false,
          requires_human_confirmation: true,
          risk_level: "medium",
          data_sources: ["ERP_live_readonly", "DuckDB"],
        },
        create_purchase_order: {
          description: "Policy without registry entry",
          read_only: false,
          requires_human_confirmation: true,
          risk_level: "high",
          data_sources: ["ERP_live_readonly"],
        },
      },
    },
    auditEvents: [
      {
        event_type: "mcp_tool_called",
        actor: "agent",
        summary: "blocked",
        created_at: "2026-05-19T08:00:00.000Z",
        risk_level: "high",
        tool_name: "sync_connector_dataset",
        skill_id: "",
      },
    ],
  });

  assert.equal(summary.tool_registry.tool_count, 2);
  assert.equal(summary.tool_registry.read_only_count, 1);
  assert.equal(summary.tool_registry.write_count, 1);
  assert.equal(summary.tool_registry.confirmation_count, 1);
  assert.equal(summary.tool_registry.high_risk_count, 1);
  assert.deepEqual(summary.tool_registry.groups, [
    "external_read",
    "write_local_state",
  ]);
  assert.deepEqual(summary.tool_registry.data_sources, [
    "DuckDB",
    "ERP_live_readonly",
  ]);

  const snapshotTool = summary.tool_registry.items.find(
    (tool) => tool.tool_name === "sync_connector_dataset",
  );
  assert.equal(snapshotTool?.mcp_policy_status, "ok");
  assert.equal(snapshotTool?.recent_call_risk, "high");
  assert.deepEqual(snapshotTool?.visible_agents, ["auto_workflow_agent"]);

  const missingRegistry = summary.mcp.items.find(
    (tool) => tool.tool_name === "create_purchase_order",
  );
  assert.equal(missingRegistry?.tool_registry_status, "registry_missing");
  assert.equal(summary.policy_validation.status, "warn");
  assert.equal(summary.policy_validation.fail_count, 0);
});

test("governance policy validation fails unsafe external writes", () => {
  const summary = summarizeGovernanceState({
    mcpPolicy: {
      tools: {
        send_external_message: {
          read_only: false,
          requires_human_confirmation: false,
          external_write_enabled: true,
          risk_level: "high",
        },
      },
    },
  });

  assert.equal(summary.policy_validation.status, "fail");
  assert.equal(summary.policy_validation.fail_count, 2);
});

test("default MCP/API policy includes WeCom smartsheet MCP read tool", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "a2a-governance-wecom-"));
  const dataDir = path.join(root, "data");
  const summary = await loadGovernanceState({
    workspaceDir: path.resolve(process.cwd(), ".."),
    dataDir,
    wikiDir: path.join(root, "wiki"),
    skillLibraryDir: path.join(root, "skills"),
    skillRegistryDir: path.join(dataDir, "skill_registry"),
    templateDir: path.join(dataDir, "agent_templates"),
    mcpPolicyPath: path.join(dataDir, "mcp", "tool_policy.json"),
    auditPath: path.join(dataDir, "audit", "events.jsonl"),
  });

  const wecomPolicy = summary.mcp.items.find(
    (tool) => tool.tool_name === "query_wecom_smartsheet_records",
  );
  assert.equal(wecomPolicy?.read_only, true);
  assert.equal(wecomPolicy?.requires_human_confirmation, false);
  assert.deepEqual(wecomPolicy?.data_sources, ["WeCom_smartsheet"]);
  assert.equal(
    wecomPolicy?.allowed_callers.includes("top_company_brain_supervisor"),
    true,
  );

  const wecomRegistry = summary.tool_registry.items.find(
    (tool) => tool.tool_name === "query_wecom_smartsheet_records",
  );
  assert.equal(wecomRegistry?.mcp_policy_status, "ok");

  const listPolicy = summary.mcp.items.find(
    (tool) => tool.tool_name === "list_wecom_smartsheet_sources",
  );
  assert.equal(listPolicy?.read_only, true);
  assert.equal(listPolicy?.requires_human_confirmation, false);

  const syncPolicy = summary.mcp.items.find(
    (tool) => tool.tool_name === "sync_wecom_smartsheet_snapshot",
  );
  assert.equal(syncPolicy?.read_only, false);
  assert.equal(syncPolicy?.requires_human_confirmation, true);
  assert.deepEqual(syncPolicy?.allowed_callers, ["auto_workflow_agent"]);
});

test("default system policy includes Agent-Reach as controlled read-only public research tools", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "a2a-governance-agent-reach-"));
  const dataDir = path.join(root, "data");
  const summary = await loadGovernanceState({
    workspaceDir: path.resolve(process.cwd(), ".."),
    dataDir,
    wikiDir: path.join(root, "wiki"),
    skillLibraryDir: path.join(root, "skills"),
    skillRegistryDir: path.join(dataDir, "skill_registry"),
    templateDir: path.join(dataDir, "agent_templates"),
    mcpPolicyPath: path.join(dataDir, "mcp", "tool_policy.json"),
    auditPath: path.join(dataDir, "audit", "events.jsonl"),
  });

  const statusPolicy = summary.mcp.items.find(
    (tool) => tool.tool_name === "agent_reach_get_status",
  );
  assert.equal(statusPolicy?.read_only, true);
  assert.equal(statusPolicy?.requires_human_confirmation, false);
  assert.deepEqual(statusPolicy?.data_sources, ["agent_reach"]);

  const publicWebPolicy = summary.mcp.items.find(
    (tool) => tool.tool_name === "agent_reach_read_public_web",
  );
  assert.equal(publicWebPolicy?.read_only, true);
  assert.equal(publicWebPolicy?.requires_human_confirmation, false);
  assert.equal(publicWebPolicy?.tool_registry_status, "ok");
  assert.equal(
    publicWebPolicy?.allowed_callers.includes("knowledge_agent"),
    true,
  );

  const socialPolicy = summary.mcp.items.find(
    (tool) => tool.tool_name === "agent_reach_read_logged_in_social",
  );
  assert.equal(socialPolicy?.read_only, true);
  assert.equal(socialPolicy?.requires_human_confirmation, true);
  assert.equal(socialPolicy?.risk_level, "medium");
  assert.equal(socialPolicy?.tool_registry_status, "ok");

  const agentReachTool = summary.tool_registry.items.find(
    (tool) => tool.tool_name === "agent_reach_search_public_sources",
  );
  assert.equal(agentReachTool?.group, "external_read");
  assert.equal(agentReachTool?.read_only, true);
  assert.equal(agentReachTool?.mcp_policy_status, "ok");
});

test("existing markdown or SKILL.md can be imported as a draft project skill", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "a2a-governance-"));
  const sourceDir = path.join(root, "skills", "DesktopSkill");
  const sourcePath = path.join(sourceDir, "SKILL.md");
  await mkdir(sourceDir, { recursive: true });
  await writeFile(
    sourcePath,
    "# 分销客户跟进\n\n用于根据客户名单、拿货排名和长时间未下单情况生成跟进建议。",
    "utf8",
  );

  const result = await createDraftSkillFromSource({
    sourcePath,
    workspaceDir: root,
    wikiDir: path.join(root, "wiki"),
    skillRegistryDir: path.join(root, "data", "skill_registry"),
    templateDir: path.join(root, "data", "agent_templates"),
    skillId: "distribution_followup",
    name: "分销客户跟进",
    scenarios: ["分销", "线下客户"],
    toolAllowlist: [
      "query_fact_layer",
      "read_wiki_page",
      "create_purchase_order",
    ],
    outputSchema: ["客户分层", "跟进动作", "数据缺口"],
    createdBy: "test",
  });

  assert.equal(result.status, "draft");
  assert.equal(result.skill.status, "draft");
  assert.equal(result.skill.tool_allowlist.includes("query_fact_layer"), true);
  assert.equal(
    result.skill.tool_allowlist.includes("create_purchase_order"),
    false,
  );
  assert.match(result.skill.source_wiki_path, /^wiki\/skills\/imported\//);

  const importedWiki = await readFile(
    path.join(root, result.skill.source_wiki_path),
    "utf8",
  );
  assert.match(importedWiki, /Imported from:/);
  assert.match(importedWiki, /分销客户跟进/);
});

test("existing Skill folder can be imported as a managed copy and updated", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "a2a-governance-folder-"));
  const sourceDir = path.join(root, "skills", "CustomerCareSkill");
  const assetPath = path.join(sourceDir, "assets", "prompt.txt");
  await mkdir(path.dirname(assetPath), { recursive: true });
  await writeFile(
    path.join(sourceDir, "SKILL.md"),
    "# 客服 SOP\n\nv1：根据售后标签和订单备注生成处理建议。",
    "utf8",
  );
  await writeFile(assetPath, "asset v1", "utf8");

  const paths = {
    workspaceDir: root,
    wikiDir: path.join(root, "wiki"),
    skillRegistryDir: path.join(root, "data", "skill_registry"),
    templateDir: path.join(root, "data", "agent_templates"),
  };
  const first = await createDraftSkillFromSource({
    sourcePath: sourceDir,
    ...paths,
    skillId: "customer_care",
    name: "客服 SOP",
    toolAllowlist: ["query_fact_layer", "create_purchase_order"],
    createdBy: "test",
  });

  assert.equal(
    (first.skill as Record<string, unknown>).source_type,
    "skill_directory",
  );
  assert.equal(first.skill.version, 0);
  const managedDir = String(
    (first.skill as Record<string, unknown>).managed_skill_dir,
  );
  assert.match(managedDir, /^data\/skill_registry\/imports\/customer_care$/);
  assert.equal(
    await readFile(path.join(root, managedDir, "assets", "prompt.txt"), "utf8"),
    "asset v1",
  );

  await writeFile(
    path.join(sourceDir, "SKILL.md"),
    "# 客服 SOP\n\nv2：加入会员等级和物流异常判断。",
    "utf8",
  );
  await writeFile(assetPath, "asset v2", "utf8");

  const second = await createDraftSkillFromSource({
    sourcePath: sourceDir,
    ...paths,
    skillId: "customer_care",
    name: "客服 SOP",
    toolAllowlist: ["query_fact_layer"],
    createdBy: "test",
  });
  const secondManagedDir = String(
    (second.skill as Record<string, unknown>).managed_skill_dir,
  );
  const record = JSON.parse(
    await readFile(
      path.join(root, "data", "skill_registry", "skills", "customer_care.json"),
      "utf8",
    ),
  );

  assert.equal(second.skill.version, 1);
  assert.equal(record.versions.length, 1);
  assert.equal(record.versions[0].version, 0);
  assert.match(record.wiki_content, /v2/);
  assert.equal(
    await readFile(
      path.join(root, secondManagedDir, "assets", "prompt.txt"),
      "utf8",
    ),
    "asset v2",
  );
});

test("skill library folder is discoverable and maps to registry imports", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "a2a-governance-library-"));
  const libraryDir = path.join(root, "skills");
  const sourceDir = path.join(libraryDir, "RetailOps");
  await mkdir(path.join(sourceDir, "assets"), { recursive: true });
  await writeFile(
    path.join(sourceDir, "SKILL.md"),
    "# 零售运营 Skill\n\n用于门店、渠道和库存联动分析。",
    "utf8",
  );
  await writeFile(path.join(sourceDir, "assets", "rules.txt"), "rules", "utf8");

  const paths = {
    workspaceDir: root,
    dataDir: path.join(root, "data"),
    wikiDir: path.join(root, "wiki"),
    skillRegistryDir: path.join(root, "data", "skill_registry"),
    templateDir: path.join(root, "data", "agent_templates"),
    mcpPolicyPath: path.join(root, "data", "mcp", "tool_policy.json"),
    auditPath: path.join(root, "data", "audit", "events.jsonl"),
    skillLibraryDir: libraryDir,
  };

  const initial = await loadGovernanceState(paths);

  assert.equal(initial.skill_library.library_path, libraryDir);
  assert.equal(initial.skill_library.item_count, 1);
  assert.equal(initial.skill_library.unregistered_count, 1);
  assert.equal(initial.skill_library.items[0].source_path, "skills/RetailOps");
  assert.equal(
    initial.skill_library.items[0].registered_status,
    "unregistered",
  );

  await createDraftSkillFromSource({
    sourcePath: "skills/RetailOps",
    workspaceDir: paths.workspaceDir,
    wikiDir: paths.wikiDir,
    skillRegistryDir: paths.skillRegistryDir,
    templateDir: paths.templateDir,
    skillId: "retail_ops",
    name: "零售运营 Skill",
    createdBy: "test",
  });

  const imported = await loadGovernanceState(paths);
  const libraryItem = imported.skill_library.items[0];

  assert.equal(imported.skill_library.registered_count, 1);
  assert.equal(libraryItem.registered_skill_id, "retail_ops");
  assert.equal(libraryItem.registered_status, "draft");
  assert.equal(
    libraryItem.managed_skill_dir,
    "data/skill_registry/imports/retail_ops",
  );
});

test("skill registration can be deleted without deleting the original folder", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "a2a-governance-delete-"));
  const sourceDir = path.join(root, "skills", "DeleteMeSkill");
  const sourceSkillPath = path.join(sourceDir, "SKILL.md");
  await mkdir(sourceDir, { recursive: true });
  await writeFile(sourceSkillPath, "# 临时 Skill\n\n需要被替换。", "utf8");

  const paths = {
    workspaceDir: root,
    dataDir: path.join(root, "data"),
    wikiDir: path.join(root, "wiki"),
    skillRegistryDir: path.join(root, "data", "skill_registry"),
    templateDir: path.join(root, "data", "agent_templates"),
    mcpPolicyPath: path.join(root, "data", "mcp", "tool_policy.json"),
    auditPath: path.join(root, "data", "audit", "events.jsonl"),
    skillLibraryDir: path.join(root, "skills"),
  };
  const imported = await createDraftSkillFromSource({
    sourcePath: sourceDir,
    workspaceDir: paths.workspaceDir,
    wikiDir: paths.wikiDir,
    skillRegistryDir: paths.skillRegistryDir,
    templateDir: paths.templateDir,
    skillId: "delete_me",
    name: "临时 Skill",
    createdBy: "test",
  });
  const managedDir = path.join(
    root,
    String((imported.skill as Record<string, unknown>).managed_skill_dir),
  );

  const result = await deleteSkillRegistration({
    paths,
    skillId: "delete_me",
    deleteManagedFiles: true,
    changedBy: "test",
  });

  assert.equal(result.status, "success");
  await assert.rejects(
    readFile(path.join(paths.skillRegistryDir, "skills", "delete_me.json")),
  );
  await assert.rejects(readFile(path.join(managedDir, "SKILL.md")));
  assert.equal(
    await readFile(sourceSkillPath, "utf8"),
    "# 临时 Skill\n\n需要被替换。",
  );
  const registry = JSON.parse(
    await readFile(path.join(paths.skillRegistryDir, "registry.json"), "utf8"),
  );
  assert.equal(registry.skills.delete_me, undefined);
});

test("registered folder skills surface missing source and can be restored from managed copy", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "a2a-governance-restore-"));
  const sourceDir = path.join(root, "skills", "RestoreMe");
  await mkdir(path.join(sourceDir, "assets"), { recursive: true });
  await writeFile(
    path.join(sourceDir, "SKILL.md"),
    "# 恢复 Skill\n\n受管副本恢复。",
    "utf8",
  );
  await writeFile(path.join(sourceDir, "assets", "rules.txt"), "rules", "utf8");

  const paths = {
    workspaceDir: root,
    dataDir: path.join(root, "data"),
    wikiDir: path.join(root, "wiki"),
    skillRegistryDir: path.join(root, "data", "skill_registry"),
    templateDir: path.join(root, "data", "agent_templates"),
    mcpPolicyPath: path.join(root, "data", "mcp", "tool_policy.json"),
    auditPath: path.join(root, "data", "audit", "events.jsonl"),
    skillLibraryDir: path.join(root, "skills"),
  };

  await createDraftSkillFromSource({
    sourcePath: "skills/RestoreMe",
    workspaceDir: paths.workspaceDir,
    wikiDir: paths.wikiDir,
    skillRegistryDir: paths.skillRegistryDir,
    templateDir: paths.templateDir,
    skillId: "restore_me",
    name: "恢复 Skill",
    createdBy: "test",
  });
  await rm(sourceDir, { recursive: true, force: true });

  const missing = await loadGovernanceState(paths);
  const missingSkill = missing.skills.items.find(
    (skill) => skill.skill_id === "restore_me",
  );

  assert.equal(missing.skill_library.item_count, 0);
  assert.equal(missingSkill?.source_status, "source_missing");
  assert.equal(missingSkill?.source_exists, false);
  assert.equal(missingSkill?.managed_source_available, true);

  const restored = await restoreSkillSourceFromManagedCopy({
    paths,
    skillId: "restore_me",
    changedBy: "test",
  });

  assert.equal(restored.status, "success");
  assert.equal(restored.source_skill_path, "skills/RestoreMe");
  assert.equal(
    await readFile(path.join(sourceDir, "assets", "rules.txt"), "utf8"),
    "rules",
  );

  const afterRestore = await loadGovernanceState(paths);
  const restoredSkill = afterRestore.skills.items.find(
    (skill) => skill.skill_id === "restore_me",
  );
  assert.equal(afterRestore.skill_library.item_count, 1);
  assert.equal(restoredSkill?.source_status, "ok");
  assert.equal(restoredSkill?.source_exists, true);
});

test("folder skill metadata supplies reimport permission defaults", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "a2a-governance-metadata-"));
  const sourceDir = path.join(root, "skills", "JackyunReadonly");
  await mkdir(sourceDir, { recursive: true });
  await writeFile(
    path.join(sourceDir, "SKILL.md"),
    "# 吉客云只读\n\n只读规则。",
    "utf8",
  );
  await writeFile(
    path.join(sourceDir, "skill.registry.json"),
    JSON.stringify(
      {
        skill_id: "jackyun_readonly",
        name: "吉客云只读",
        scenarios: ["吉客云", "库存"],
        tool_allowlist: [
          "route_erp_live_query",
          "query_inventory_cost_reference",
        ],
        output_schema: ["inventory", "data_gaps"],
      },
      null,
      2,
    ),
    "utf8",
  );

  const paths = {
    workspaceDir: root,
    dataDir: path.join(root, "data"),
    wikiDir: path.join(root, "wiki"),
    skillRegistryDir: path.join(root, "data", "skill_registry"),
    templateDir: path.join(root, "data", "agent_templates"),
    mcpPolicyPath: path.join(root, "data", "mcp", "tool_policy.json"),
    auditPath: path.join(root, "data", "audit", "events.jsonl"),
    skillLibraryDir: path.join(root, "skills"),
  };

  const imported = await createDraftSkillFromSource({
    sourcePath: "skills/JackyunReadonly",
    workspaceDir: paths.workspaceDir,
    wikiDir: paths.wikiDir,
    skillRegistryDir: paths.skillRegistryDir,
    templateDir: paths.templateDir,
    createdBy: "test",
  });
  const skill = imported.skill as Record<string, unknown>;

  assert.equal(skill.skill_id, "jackyun_readonly");
  assert.equal(skill.name, "吉客云只读");
  assert.deepEqual(skill.scenarios, ["吉客云", "库存"]);
  assert.deepEqual(skill.tool_allowlist, [
    "route_erp_live_query",
    "query_inventory_cost_reference",
  ]);
  assert.deepEqual(skill.output_schema, ["inventory", "data_gaps"]);
});

test("MCP/API policy can be added without enabling direct writes", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "a2a-governance-mcp-"));
  const policyPath = path.join(root, "data", "mcp", "tool_policy.json");

  const result = await upsertMcpToolPolicy({
    policyPath,
    toolName: "send_wecom_message",
    description: "企业微信外发消息",
    action: "write_external_message",
    readOnly: false,
    requiresHumanConfirmation: true,
    riskLevel: "high",
    dataSources: ["wecom"],
    allowedCallers: ["auto_workflow_agent"],
    destructiveEffects: ["会触达外部人员。"],
  });

  assert.equal(result.status, "success");
  assert.equal(result.tool.read_only, false);
  assert.equal(result.tool.requires_human_confirmation, true);

  const stored = JSON.parse(await readFile(policyPath, "utf8"));
  assert.equal(stored.tools.send_wecom_message.risk_level, "high");
  assert.equal(
    stored.tools.send_wecom_message.requires_human_confirmation,
    true,
  );
});

test("skill import rejects workspace-external paths and symlink escapes", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "a2a-governance-paths-"));
  const outside = await mkdtemp(path.join(tmpdir(), "a2a-governance-outside-"));
  const outsideSkill = path.join(outside, "SKILL.md");
  await writeFile(outsideSkill, "# 外部 Skill\n\n不应导入。", "utf8");
  await mkdir(path.join(root, "skills"), { recursive: true });
  await symlink(outside, path.join(root, "skills", "EscapeSkill"));

  const paths = {
    workspaceDir: root,
    wikiDir: path.join(root, "wiki"),
    skillRegistryDir: path.join(root, "data", "skill_registry"),
    templateDir: path.join(root, "data", "agent_templates"),
  };

  await assert.rejects(
    createDraftSkillFromSource({
      sourcePath: outsideSkill,
      ...paths,
      skillId: "outside",
    }),
    /允许导入技能的目录/,
  );
  await assert.rejects(
    createDraftSkillFromSource({
      sourcePath: "skills/EscapeSkill",
      ...paths,
      skillId: "escape",
    }),
    /允许导入技能的目录/,
  );
});

test("MCP policy upsert forces write-like actions behind confirmation", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "a2a-governance-policy-"));
  const policyPath = path.join(root, "data", "mcp", "tool_policy.json");
  const result = await upsertMcpToolPolicy({
    policyPath,
    toolName: "send_external_message",
    description: "send",
    action: "write_external_send",
    readOnly: true,
    requiresHumanConfirmation: false,
    riskLevel: "low",
    dataSources: ["erp"],
    allowedCallers: ["unknown_agent"],
    destructiveEffects: [],
  });

  assert.equal(result.tool.action, "write_external_send");
  assert.equal(result.tool.read_only, false);
  assert.equal(result.tool.requires_human_confirmation, true);
  assert.equal(result.tool.risk_level, "high");
  assert.equal(result.tool.external_write_enabled, false);
  assert.deepEqual(result.tool.allowed_callers, []);
});
