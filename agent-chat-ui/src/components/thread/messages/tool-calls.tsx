import { AIMessage, ToolMessage } from "@langchain/langgraph-sdk";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { AlertTriangle, Check, ChevronDown, ChevronUp, Copy, PlayCircle } from "lucide-react";

function isComplexValue(value: any): boolean {
  return Array.isArray(value) || (typeof value === "object" && value !== null);
}

function ConfirmationRequiredCard({
  payload,
}: {
  payload: Record<string, any>;
}) {
  const [copied, setCopied] = useState(false);
  const token = String(
    payload.confirmation_token ?? payload.required_confirm_phrase ?? "",
  );
  const effects = Array.isArray(payload.destructive_effects)
    ? payload.destructive_effects
    : [];
  const preview = payload.preview ?? {};
  const candidateCount =
    payload.candidate_count ??
    preview.recoverable_timeout_count ??
    preview.source_failed_count ??
    0;

  const copyToken = async () => {
    if (!token) return;
    await navigator.clipboard.writeText(token);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  };
  const fillConfirmPrompt = () => {
    if (!token) return;
    const action = String(payload.action ?? "LightRAG 确认操作");
    window.dispatchEvent(
      new CustomEvent("a2a-fill-chat-input", {
        detail: `确认执行 ${action}，confirmation_token=${token}`,
      }),
    );
  };

  return (
    <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-amber-950">
      <div className="flex items-start gap-2">
        <AlertTriangle className="mt-0.5 size-4 shrink-0" />
        <div className="min-w-0 flex-1">
          <div className="text-sm font-semibold">需要人工确认</div>
          <p className="mt-1 text-sm text-amber-900">
            这个 LightRAG 操作会影响 failed 记录或提交恢复摘要。当前只展示预览，尚未执行清理。
          </p>
          <div className="mt-2 grid gap-1 text-xs">
            <div>Action: {String(payload.action ?? "lightrag_confirmation")}</div>
            <div>候选影响数量: {String(candidateCount)}</div>
          </div>
          {effects.length > 0 && (
            <ul className="mt-2 list-disc space-y-1 pl-5 text-xs">
              {effects.slice(0, 4).map((effect: unknown, index: number) => (
                <li key={index}>{String(effect)}</li>
              ))}
            </ul>
          )}
          {token && (
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={fillConfirmPrompt}
                className="inline-flex h-8 items-center gap-2 rounded-md border border-amber-300 bg-amber-900 px-2.5 text-xs font-medium text-white hover:bg-amber-800"
              >
                <PlayCircle className="size-3.5" />
                填入确认指令
              </button>
              <button
                type="button"
                onClick={copyToken}
                className="inline-flex h-8 items-center gap-2 rounded-md border border-amber-300 bg-white px-2.5 text-xs font-medium text-amber-950 hover:bg-amber-100"
              >
                {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
                {copied ? "已复制 token" : "复制 token"}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export function ToolCalls({
  toolCalls,
}: {
  toolCalls: AIMessage["tool_calls"];
}) {
  if (!toolCalls || toolCalls.length === 0) return null;

  return (
    <div className="mx-auto grid max-w-3xl grid-rows-[1fr_auto] gap-2">
      {toolCalls.map((tc, idx) => {
        const args = tc.args as Record<string, any>;
        const hasArgs = Object.keys(args).length > 0;
        return (
          <div
            key={idx}
            className="overflow-hidden rounded-lg border border-gray-200"
          >
            <div className="border-b border-gray-200 bg-gray-50 px-4 py-2">
              <h3 className="font-medium text-gray-900">
                {tc.name}
                {tc.id && (
                  <code className="ml-2 rounded bg-gray-100 px-2 py-1 text-sm">
                    {tc.id}
                  </code>
                )}
              </h3>
            </div>
            {hasArgs ? (
              <table className="min-w-full divide-y divide-gray-200">
                <tbody className="divide-y divide-gray-200">
                  {Object.entries(args).map(([key, value], argIdx) => (
                    <tr key={argIdx}>
                      <td className="px-4 py-2 text-sm font-medium whitespace-nowrap text-gray-900">
                        {key}
                      </td>
                      <td className="px-4 py-2 text-sm text-gray-500">
                        {isComplexValue(value) ? (
                          <code className="rounded bg-gray-50 px-2 py-1 font-mono text-sm break-all">
                            {JSON.stringify(value, null, 2)}
                          </code>
                        ) : (
                          String(value)
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <code className="block p-3 text-sm">{"{}"}</code>
            )}
          </div>
        );
      })}
    </div>
  );
}

export function ToolResult({ message }: { message: ToolMessage }) {
  const [isExpanded, setIsExpanded] = useState(false);

  let parsedContent: any;
  let isJsonContent = false;

  try {
    if (typeof message.content === "string") {
      parsedContent = JSON.parse(message.content);
      isJsonContent = isComplexValue(parsedContent);
    }
  } catch {
    // Content is not JSON, use as is
    parsedContent = message.content;
  }

  const contentStr = isJsonContent
    ? JSON.stringify(parsedContent, null, 2)
    : String(message.content);
  const contentLines = contentStr.split("\n");
  const shouldTruncate = contentLines.length > 4 || contentStr.length > 500;
  const displayedContent =
    shouldTruncate && !isExpanded
      ? contentStr.length > 500
        ? contentStr.slice(0, 500) + "..."
        : contentLines.slice(0, 4).join("\n") + "\n..."
      : contentStr;

  return (
    <div className="mx-auto grid max-w-3xl grid-rows-[1fr_auto] gap-2">
      <div className="overflow-hidden rounded-lg border border-gray-200">
        <div className="border-b border-gray-200 bg-gray-50 px-4 py-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            {message.name ? (
              <h3 className="font-medium text-gray-900">
                Tool Result:{" "}
                <code className="rounded bg-gray-100 px-2 py-1">
                  {message.name}
                </code>
              </h3>
            ) : (
              <h3 className="font-medium text-gray-900">Tool Result</h3>
            )}
            {message.tool_call_id && (
              <code className="ml-2 rounded bg-gray-100 px-2 py-1 text-sm">
                {message.tool_call_id}
              </code>
            )}
          </div>
        </div>
        <motion.div
          className="min-w-full bg-gray-100"
          initial={false}
          animate={{ height: "auto" }}
          transition={{ duration: 0.3 }}
        >
          <div className="p-3">
            <AnimatePresence
              mode="wait"
              initial={false}
            >
              <motion.div
                key={isExpanded ? "expanded" : "collapsed"}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                transition={{ duration: 0.2 }}
              >
                {isJsonContent &&
                parsedContent &&
                typeof parsedContent === "object" &&
                parsedContent.requires_confirmation ? (
                  <div className="space-y-3">
                    <ConfirmationRequiredCard payload={parsedContent} />
                    <pre className="max-h-80 overflow-auto rounded bg-gray-50 p-3 text-xs whitespace-pre-wrap text-gray-700">
                      {JSON.stringify(parsedContent, null, 2)}
                    </pre>
                  </div>
                ) : isJsonContent ? (
                  <table className="min-w-full divide-y divide-gray-200">
                    <tbody className="divide-y divide-gray-200">
                      {(Array.isArray(parsedContent)
                        ? isExpanded
                          ? parsedContent
                          : parsedContent.slice(0, 5)
                        : Object.entries(parsedContent)
                      ).map((item, argIdx) => {
                        const [key, value] = Array.isArray(parsedContent)
                          ? [argIdx, item]
                          : [item[0], item[1]];
                        return (
                          <tr key={argIdx}>
                            <td className="px-4 py-2 text-sm font-medium whitespace-nowrap text-gray-900">
                              {key}
                            </td>
                            <td className="px-4 py-2 text-sm text-gray-500">
                              {isComplexValue(value) ? (
                                <code className="rounded bg-gray-50 px-2 py-1 font-mono text-sm break-all">
                                  {JSON.stringify(value, null, 2)}
                                </code>
                              ) : (
                                String(value)
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                ) : (
                  <code className="block text-sm">{displayedContent}</code>
                )}
              </motion.div>
            </AnimatePresence>
          </div>
          {((shouldTruncate && !isJsonContent) ||
            (isJsonContent &&
              Array.isArray(parsedContent) &&
              parsedContent.length > 5)) && (
            <motion.button
              onClick={() => setIsExpanded(!isExpanded)}
              className="flex w-full cursor-pointer items-center justify-center border-t-[1px] border-gray-200 py-2 text-gray-500 transition-all duration-200 ease-in-out hover:bg-gray-50 hover:text-gray-600"
              initial={{ scale: 1 }}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
            >
              {isExpanded ? <ChevronUp /> : <ChevronDown />}
            </motion.button>
          )}
        </motion.div>
      </div>
    </div>
  );
}
