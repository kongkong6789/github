import assert from "node:assert/strict";
import { mkdir, mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { test } from "node:test";

import {
  checkSkillhubStatus,
  installSkillhubSkill,
  listSkillhubCatalog,
  searchSkillhubSkills,
  type SkillhubRunner,
} from "./skillhub";

test("SkillHub status reports an unavailable CLI without throwing", async () => {
  const status = await checkSkillhubStatus({
    candidates: ["missing-skillhub"],
    runner: async () => {
      throw new Error("spawn ENOENT");
    },
  });

  assert.equal(status.available, false);
  assert.equal(status.status, "unavailable");
  assert.match(status.error, /spawn ENOENT/);
  assert.match(status.install_command, /已禁用/);
});

test("SkillHub status uses a lightweight version check", async () => {
  const calls: Array<{ command: string; args: string[] }> = [];
  const status = await checkSkillhubStatus({
    candidates: ["skillhub"],
    runner: async (command, args) => {
      calls.push({ command, args });
      return { stdout: "skillhub 2026.5.29\n", stderr: "" };
    },
  });

  assert.deepEqual(calls, [{ command: "skillhub", args: ["-v"] }]);
  assert.equal(status.available, true);
  assert.equal(status.version, "skillhub 2026.5.29");
});

test("SkillHub search uses json output and normalizes CLI results", async () => {
  const calls: Array<{ command: string; args: string[] }> = [];
  const runner: SkillhubRunner = async (command, args) => {
    calls.push({ command, args });
    return {
      stdout: JSON.stringify({
        query: "库存",
        count: 1,
        results: [
          {
            slug: "inventory-analyst",
            name: "库存分析",
            description: "库存、补货和动销分析 Skill",
            version: "1.2.0",
            source: "community",
          },
        ],
        warnings: ["community cache"],
      }),
      stderr: "",
    };
  };

  const result = await searchSkillhubSkills({
    query: "库存",
    command: "skillhub",
    runner,
    limit: 12,
  });

  assert.deepEqual(calls, [
    {
      command: "skillhub",
      args: ["search", "库存", "--json", "--search-limit", "12"],
    },
  ]);
  assert.equal(result.status, "success");
  assert.equal(result.count, 1);
  assert.equal(result.results[0].slug, "inventory-analyst");
  assert.equal(result.results[0].name, "库存分析");
  assert.deepEqual(result.warnings, ["community cache"]);
});

test("SkillHub search forwards larger requested limits", async () => {
  const calls: Array<{ command: string; args: string[] }> = [];
  const runner: SkillhubRunner = async (command, args) => {
    calls.push({ command, args });
    return {
      stdout: JSON.stringify({
        query: "市场调研",
        count: 80,
        results: [],
        warnings: [],
      }),
      stderr: "",
    };
  };

  await searchSkillhubSkills({
    query: "市场调研",
    command: "skillhub",
    runner,
    limit: 100,
  });

  assert.deepEqual(calls[0].args, [
    "search",
    "市场调研",
    "--json",
    "--search-limit",
    "100",
  ]);
});

test("SkillHub search retries transient community failures", async () => {
  let attempts = 0;
  const runner: SkillhubRunner = async () => {
    attempts += 1;
    if (attempts === 1) {
      return {
        stdout: "No skills found.\n",
        stderr: "⚠️  community: search request failed\n",
      };
    }
    return {
      stdout: JSON.stringify({
        query: "市场调研",
        count: 1,
        results: [{ slug: "marketresearch", name: "市场调研" }],
        warnings: [],
      }),
      stderr: "",
    };
  };

  const result = await searchSkillhubSkills({
    query: "市场调研",
    command: "skillhub",
    runner,
    limit: 50,
  });

  assert.equal(attempts, 2);
  assert.equal(result.results[0].slug, "marketresearch");
});

test("SkillHub catalog sorts and filters rich marketplace metadata", async () => {
  let requestedUrl = "";
  const result = await listSkillhubCatalog({
    query: "市场",
    category: "data-analysis",
    source: "community",
    sort: "downloads",
    limit: 2,
    fetchJson: async (url) => {
      requestedUrl = url;
      return {
        results: [
          {
            slug: "low-download",
            displayName: "低下载",
            summary: "市场分析",
            source: "community",
            category: "data-analysis",
            tags: ["market"],
            downloads: 20,
            installs: 8,
            stars: 3,
            score: 0.8,
            updated_at: 1780200000000,
            version: "1.0.0",
          },
          {
            slug: "other-source",
            displayName: "其他来源",
            source: "clawhub",
            category: "data-analysis",
            downloads: 999,
          },
          {
            slug: "high-download",
            displayName: "高下载",
            summary: "高下载市场分析",
            source: "community",
            categories: ["data-analysis", "AI增强"],
            downloads: 300,
            installs: 90,
            stars: 18,
            score: 0.3,
            updatedAt: 1780300000000,
            version: "1.2.0",
          },
        ],
      };
    },
  });

  assert.equal(result.status, "success");
  assert.match(requestedUrl, /limit=100/);
  assert.equal(result.results.length, 2);
  assert.deepEqual(
    result.results.map((item) => item.slug),
    ["high-download", "low-download"],
  );
  assert.equal(result.results[0].downloads, 300);
  assert.equal(result.results[0].installs, 90);
  assert.equal(result.results[0].stars, 18);
  assert.deepEqual(result.results[0].categories, ["data-analysis", "AI增强"]);
  assert.equal(result.sources.includes("community"), true);
  assert.equal(result.categories.includes("data-analysis"), true);
});

test("SkillHub catalog treats skillhub source as the public marketplace", async () => {
  const result = await listSkillhubCatalog({
    source: "skillhub",
    fetchJson: async () => ({
      results: [
        {
          slug: "community-skill",
          displayName: "Community Skill",
          source: "community",
          score: 20,
        },
        {
          slug: "clawhub-skill",
          displayName: "ClawHub Skill",
          source: "clawhub",
          score: 30,
        },
        {
          slug: "enterprise-skill",
          displayName: "Enterprise Skill",
          source: "enterprise",
          score: 40,
        },
      ],
    }),
  });

  assert.equal(result.count, 2);
  assert.deepEqual(
    result.results.map((item) => item.slug),
    ["clawhub-skill", "community-skill"],
  );
});

test("SkillHub catalog exposes and filters SkillHub category metadata", async () => {
  const fetchJson = async () => ({
    results: [
      {
        slug: "self-improving-agent",
        displayName: "Self-Improving Agent",
        source: "clawhub",
        category: "ai-intelligence",
        score: 50,
      },
      {
        slug: "github",
        displayName: "Github",
        source: "clawhub",
        category: "developer-tools",
        score: 40,
      },
      {
        slug: "multi-search-engine",
        displayName: "Multi Search Engine",
        summary: "Search the web across multiple engines.",
        source: "clawhub",
        category: "productivity",
        score: 30,
      },
      {
        slug: "analytics-suite",
        displayName: "Analytics Suite",
        source: "clawhub",
        categories: ["data-analysis", "productivity"],
        score: 20,
      },
      {
        slug: "enterprise-only",
        displayName: "Enterprise Only",
        source: "enterprise",
        category: "enterprise-category",
        score: 5,
      },
    ],
  });

  const all = await listSkillhubCatalog({
    source: "skillhub",
    fetchJson,
  });
  assert.deepEqual(all.categories, [
    "ai-intelligence",
    "data-analysis",
    "developer-tools",
    "productivity",
  ]);

  const ai = await listSkillhubCatalog({
    category: "ai-intelligence",
    source: "skillhub",
    fetchJson,
  });
  assert.deepEqual(
    ai.results.map((item) => item.slug),
    ["self-improving-agent"],
  );

  const productivity = await listSkillhubCatalog({
    category: "productivity",
    source: "skillhub",
    fetchJson,
  });
  assert.deepEqual(
    productivity.results.map((item) => item.slug),
    ["multi-search-engine", "analytics-suite"],
  );

  const dataAnalysis = await listSkillhubCatalog({
    category: "data-analysis",
    source: "skillhub",
    fetchJson,
  });
  assert.deepEqual(
    dataAnalysis.results.map((item) => item.slug),
    ["analytics-suite"],
  );

  const localOnlyCategory = await listSkillhubCatalog({
    category: "search-research",
    source: "skillhub",
    fetchJson,
  });
  assert.deepEqual(localOnlyCategory.results, []);
});

test("SkillHub catalog can load the featured index without a query", async () => {
  const result = await listSkillhubCatalog({
    query: "",
    sort: "score",
    limit: 1,
    fetchJson: async (url) => {
      assert.match(url, /skills\.json$/);
      return {
        total: 1,
        skills: [
          {
            slug: "featured",
            name: "Featured Skill",
            categories: ["AI增强"],
            downloads: 10,
            stars: 5,
            score: 42,
          },
        ],
      };
    },
  });

  assert.equal(result.query, "");
  assert.equal(result.results[0].slug, "featured");
  assert.equal(result.results[0].score, 42);
});

test("SkillHub catalog falls back to search API when featured index is empty", async () => {
  const requestedUrls: string[] = [];
  const result = await listSkillhubCatalog({
    query: "",
    source: "community",
    limit: 1,
    fetchJson: async (url) => {
      requestedUrls.push(url);
      if (url.endsWith("skills.json")) {
        return { total: 0, skills: [] };
      }
      return {
        results: [
          {
            slug: "clawhub-skill",
            displayName: "ClawHub Skill",
            source: "clawhub",
            score: 100,
          },
          {
            slug: "community-skill",
            displayName: "Community Skill",
            source: "community",
            score: 90,
          },
        ],
      };
    },
  });

  assert.equal(requestedUrls.length, 2);
  assert.match(requestedUrls[0], /skills\.json$/);
  assert.match(requestedUrls[1], /api\.skillhub\.cn\/api\/v1\/search/);
  assert.match(requestedUrls[1], /limit=100/);
  assert.equal(result.count, 1);
  assert.equal(result.results[0].slug, "community-skill");
});

test("SkillHub install writes into project skills and imports a draft skill", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "a2a-skillhub-"));
  const paths = {
    workspaceDir: root,
    dataDir: path.join(root, "data"),
    wikiDir: path.join(root, "wiki"),
    skillLibraryDir: path.join(root, "skills"),
    skillRegistryDir: path.join(root, "data", "skill_registry"),
    templateDir: path.join(root, "data", "agent_templates"),
    mcpPolicyPath: path.join(root, "data", "mcp", "tool_policy.json"),
    auditPath: path.join(root, "data", "audit", "events.jsonl"),
  };
  await mkdir(paths.skillLibraryDir, { recursive: true });

  const runner: SkillhubRunner = async (command, args) => {
    assert.equal(command, "skillhub");
    assert.deepEqual(args, [
      "install",
      "inventory-analyst",
      "--json",
      "--dir",
      paths.skillLibraryDir,
      "--force",
    ]);
    const targetDir = path.join(paths.skillLibraryDir, "inventory-analyst");
    await mkdir(targetDir, { recursive: true });
    await writeFile(
      path.join(targetDir, "SKILL.md"),
      "# SkillHub 库存分析\n\n从 SkillHub 安装后进入项目草稿流。",
      "utf8",
    );
    return {
      stdout: JSON.stringify({
        success: true,
        slug: "inventory-analyst",
        name: "库存分析",
        version: "1.2.0",
        source: "community",
        targetDir,
      }),
      stderr: "",
    };
  };

  const result = await installSkillhubSkill({
    slug: "inventory-analyst",
    command: "skillhub",
    paths,
    runner,
    force: true,
  });

  assert.equal(result.status, "success");
  assert.equal(result.install.slug, "inventory-analyst");
  assert.equal(result.draft.status, "draft");
  assert.equal(result.draft.skill.skill_id, "skillhub-inventory-analyst");
  assert.equal(result.draft.skill.status, "draft");
  assert.equal(
    result.draft.skill.source_skill_path,
    "skills/inventory-analyst",
  );

  const registryRecord = JSON.parse(
    await readFile(
      path.join(
        paths.skillRegistryDir,
        "skills",
        "skillhub-inventory-analyst.json",
      ),
      "utf8",
    ),
  );
  assert.match(registryRecord.wiki_content, /SkillHub 库存分析/);
});
