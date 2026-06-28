export type FriendlyStreamError = {
  title: string;
  description: string;
  rawMessage: string;
};

export function getErrorMessage(error: unknown): string {
  if (typeof error === "string") return error;
  if (error instanceof Error) return error.message;
  if (error && typeof error === "object" && "message" in error) {
    const message = (error as { message?: unknown }).message;
    if (typeof message === "string") return message;
  }
  return String(error ?? "未知错误");
}

function getErrorName(error: unknown): string {
  if (error instanceof Error) return error.name;
  if (error && typeof error === "object" && "name" in error) {
    const name = (error as { name?: unknown }).name;
    if (typeof name === "string") return name;
  }
  return "";
}

export function toFriendlyStreamError(error: unknown): FriendlyStreamError {
  const rawMessage = getErrorMessage(error);
  const normalized = `${getErrorName(error)} ${rawMessage}`.toLowerCase();

  if (
    normalized.includes("messages with role 'tool'") ||
    normalized.includes('messages with role "tool"')
  ) {
    return {
      title: "对话历史异常，系统已自动保护",
      description:
        "这通常是旧对话里残留了不完整的工具调用记录。系统会在后端自动清洗后重试；如果仍失败，请新开一个对话继续。",
      rawMessage,
    };
  }

  if (
    normalized.includes("network error") ||
    normalized.includes("failed to fetch") ||
    normalized.includes("fetch failed")
  ) {
    return {
      title: "连接后端失败",
      description:
        "请确认 LangGraph 后端仍在运行，然后重试。当前消息没有必要重复改写。",
      rawMessage,
    };
  }

  if (
    normalized.includes("internal error occurred")
  ) {
    return {
      title: "后端执行中断",
      description:
        "系统已经拦截开发报错页。请直接重试一次；如果持续出现，请让管理员查看后端日志里的具体工具错误。",
      rawMessage,
    };
  }

  if (
    normalized.includes("badrequesterror") ||
    normalized.includes("bad request")
  ) {
    return {
      title: "请求被模型服务拒绝",
      description:
        "系统已经拦截开发报错页。请直接重试一次；如果持续出现，建议开启新对话或让管理员查看后端日志。",
      rawMessage,
    };
  }

  return {
    title: "请求处理失败",
    description: "请稍后重试；如果重复失败，请让管理员查看后端日志。",
    rawMessage,
  };
}

export function shouldSuppressStreamConsoleError(error: unknown): boolean {
  const rawMessage = getErrorMessage(error).toLowerCase();
  const name = getErrorName(error).toLowerCase();
  return (
    name.includes("badrequesterror") ||
    rawMessage.includes("an internal error occurred") ||
    rawMessage.includes("network error") ||
    rawMessage.includes("failed to fetch") ||
    rawMessage.includes("fetch failed") ||
    rawMessage.includes("messages with role 'tool'") ||
    rawMessage.includes('messages with role "tool"')
  );
}
