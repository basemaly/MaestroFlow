"use client";

import { useParams, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { isUuid, uuid } from "@/core/utils/uuid";

export function useThreadChat() {
  const { thread_id: threadIdFromPath } = useParams<{ thread_id: string }>();
  const isRouteThreadIdValid =
    !threadIdFromPath ||
    threadIdFromPath === "new" ||
    isUuid(threadIdFromPath);

  const searchParams = useSearchParams();
  const [threadId, setThreadId] = useState(() => {
    if (!threadIdFromPath || threadIdFromPath === "new") {
      return "new";
    }
    return isUuid(threadIdFromPath) ? threadIdFromPath : "new";
  });

  const [isNewThread, setIsNewThread] = useState(
    () => threadIdFromPath === "new" || !isRouteThreadIdValid,
  );

  useEffect(() => {
    if (threadIdFromPath === "new" || !isRouteThreadIdValid) {
      setIsNewThread(true);
      setThreadId((current) => (current === "new" ? uuid() : current));
      return;
    }
    if (threadIdFromPath) {
      setThreadId(threadIdFromPath);
    }
    setIsNewThread(false);
  }, [isRouteThreadIdValid, threadIdFromPath]);
  const isMock = searchParams.get("mock") === "true";
  return {
    threadId,
    isNewThread,
    setIsNewThread,
    isMock,
    isInvalidThreadRoute: !isRouteThreadIdValid,
  };
}
