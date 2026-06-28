"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, type ReactNode } from "react";
import gsap from "gsap";
import { ShieldEllipsis } from "lucide-react";

import { cn } from "@/lib/utils";
import { isActiveWorkbenchPath, workbenchNavItems } from "@/lib/workbench-nav";

function WorkbenchSidebar() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const currentSearch = searchParams.toString();

  return (
    <aside
      className="relative z-10 hidden min-h-screen w-[15rem] shrink-0 border-r border-[#d9dceb] bg-[#e4e1e6] px-3 py-6 xl:flex xl:flex-col"
      data-workbench-motion="enter"
    >
      <Link
        href="/"
        className="group flex items-center gap-3 rounded-xl px-3 py-2.5 text-left transition hover:bg-white/55"
        aria-label="返回 A2A 经营大脑"
      >
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-[#004ac6] text-sm font-black text-white shadow-[0_12px_24px_rgba(0,74,198,0.22)]">
          A2A
        </span>
        <span className="min-w-0">
          <span className="block truncate text-base font-semibold text-[#191b23]">
            A2A 经营大脑
          </span>
          <span className="mt-0.5 block text-xs text-[#5f6372]">
            经营工作台
          </span>
        </span>
      </Link>

      <nav className="mt-7 grid gap-1">
        {workbenchNavItems.map((item) => {
          const active = isActiveWorkbenchPath(
            pathname,
            item.href,
            currentSearch,
          );
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              title={`${item.label} - ${item.description}`}
              aria-label={item.label}
              className={cn(
                "group flex min-h-10 items-center gap-3 rounded-lg px-3 py-2 text-left text-sm transition",
                active
                  ? "bg-[#004ac6] font-medium text-white shadow-[0_10px_24px_rgba(0,74,198,0.2)]"
                  : "text-[#434655] hover:bg-white/55 hover:text-[#191b23]",
              )}
            >
              <span
                className={cn(
                  "grid size-5 place-items-center",
                  active ? "text-white" : "text-[#5f6372]",
                )}
              >
                <Icon className="size-4" />
              </span>
              <span className="min-w-0 truncate">
                {item.label}
              </span>
            </Link>
          );
        })}
      </nav>

      <div className="mt-auto rounded-xl border border-[#d9dceb] bg-white/65 p-3">
        <div className="flex items-center gap-2 text-[#004ac6]">
          <ShieldEllipsis className="size-5" />
          <span className="text-sm font-semibold">本地工作区</span>
        </div>
        <p className="mt-2 text-xs leading-5 text-[#5f6372]">
          资料、任务和技能配置保留在当前项目工作区内。
        </p>
      </div>
    </aside>
  );
}

function MobileNav() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const currentSearch = searchParams.toString();

  return (
    <div
      className="relative z-10 flex gap-2 overflow-x-auto border-b border-[#d9dceb] bg-[#e4e1e6] px-4 py-3 xl:hidden"
      data-workbench-motion="enter"
    >
      {workbenchNavItems.map((item) => {
        const active = isActiveWorkbenchPath(
          pathname,
          item.href,
          currentSearch,
        );
        const Icon = item.icon;
        return (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "inline-flex min-h-10 shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-sm transition",
              active
                ? "bg-[#004ac6] text-white"
                : "bg-white/65 text-[#434655] hover:bg-white",
            )}
          >
            <Icon className="size-4" />
            {item.label}
          </Link>
        );
      })}
    </div>
  );
}

export function WorkbenchShell({
  title,
  description,
  status,
  actions,
  children,
}: {
  title: string;
  description?: string;
  status?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
}) {
  const shellRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const root = shellRef.current;
    if (!root) return;

    const prefersReducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;

    if (prefersReducedMotion) return;

    const scanTargets = root.querySelectorAll("[data-workbench-motion='scan']");
    const orbitTargets = root.querySelectorAll(
      "[data-workbench-motion='orbit']",
    );
    const animatedTargets = [
      ...Array.from(scanTargets),
      ...Array.from(orbitTargets),
    ];
    const frame = window.requestAnimationFrame(() => {
      if (scanTargets.length > 0) {
        gsap.to(scanTargets, {
          xPercent: 18,
          opacity: 0.85,
          duration: 4.8,
          ease: "sine.inOut",
          repeat: -1,
          yoyo: true,
        });
      }

      if (orbitTargets.length > 0) {
        gsap.to(orbitTargets, {
          rotate: 360,
          duration: 28,
          ease: "none",
          repeat: -1,
        });
      }
    });

    return () => {
      window.cancelAnimationFrame(frame);
      gsap.killTweensOf(animatedTargets);
    };
  }, []);

  return (
    <main
      ref={shellRef}
      className="workbench-shell relative min-h-screen overflow-hidden bg-[#faf8ff] text-[#191b23]"
    >
      <div
        className="pointer-events-none fixed inset-0 z-0 overflow-hidden"
        aria-hidden="true"
      >
        <div className="workbench-grid absolute inset-0" />
      </div>
      <div className="flex min-h-screen">
        <Suspense fallback={null}>
          <WorkbenchSidebar />
        </Suspense>
        <section className="relative z-10 flex min-w-0 flex-1 flex-col">
          <Suspense fallback={null}>
            <MobileNav />
          </Suspense>
          <div
            className="sticky top-0 z-20 border-b border-[#d9dceb] bg-[#faf8ff]/90 px-4 py-4 backdrop-blur-xl lg:px-6"
            data-workbench-motion="enter"
          >
            <div className="mx-auto flex max-w-[1500px] flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h1 className="text-2xl font-semibold tracking-normal text-[#191b23] md:text-3xl">
                    {title}
                  </h1>
                  {status}
                </div>
                {description && (
                  <p className="mt-1 max-w-3xl text-sm leading-6 text-[#5f6372]">
                    {description}
                  </p>
                )}
              </div>
              {actions && (
                <div className="flex shrink-0 flex-wrap items-center gap-2">
                  {actions}
                </div>
              )}
            </div>
          </div>
          <div
            className="mx-auto w-full max-w-[1500px] flex-1 px-4 py-5 lg:px-6 lg:py-6"
            data-workbench-motion="enter"
          >
            {children}
          </div>
        </section>
      </div>
    </main>
  );
}

export function WorkbenchPanel({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={cn(
        "rounded-[18px] border border-[#d9dceb] bg-white shadow-[0_16px_40px_rgba(25,27,35,0.06)]",
        className,
      )}
    >
      {children}
    </section>
  );
}

export function WorkbenchCard({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "rounded-[18px] border border-[#d9dceb] bg-white p-4 shadow-[0_12px_32px_rgba(25,27,35,0.05)]",
        className,
      )}
    >
      {children}
    </div>
  );
}
