"use client";

import { useEffect, useRef, useState } from "react";
import { Play, Pause, SkipBack, SkipForward, Layers } from "lucide-react";
import type { TraceFrame } from "@/lib/types";

interface StateVisualizerProps {
  frames: TraceFrame[];
  supported: boolean;
  message: string | null;
}

export default function StateVisualizer({ frames, supported, message }: StateVisualizerProps) {
  const [index, setIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [speedMs, setSpeedMs] = useState(500);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Reset to the first frame whenever a fresh trace comes in. Adjusting
  // state during render (rather than in an effect) avoids an extra
  // cascading render pass — see https://react.dev/learn/you-might-not-need-an-effect
  const [prevFrames, setPrevFrames] = useState(frames);
  if (frames !== prevFrames) {
    setPrevFrames(frames);
    setIndex(0);
    setIsPlaying(false);
  }

  useEffect(() => {
    if (!isPlaying) {
      if (intervalRef.current) clearInterval(intervalRef.current);
      return;
    }
    intervalRef.current = setInterval(() => {
      setIndex((prev) => {
        if (prev >= frames.length - 1) {
          setIsPlaying(false);
          return prev;
        }
        return prev + 1;
      });
    }, speedMs);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [isPlaying, speedMs, frames.length]);

  if (!supported) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 p-6 text-center">
        <Layers className="h-6 w-6 text-paper/30" />
        <p className="max-w-md text-sm text-paper/50">{message}</p>
      </div>
    );
  }

  if (frames.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-paper/40">
        Run your code to see live variable, array, and call-stack state here.
      </div>
    );
  }

  const frame = frames[Math.min(index, frames.length - 1)];
  const pointerByIndex = new Map<number, string[]>();
  Object.entries(frame.pointers).forEach(([name, idx]) => {
    const list = pointerByIndex.get(idx) ?? [];
    list.push(name);
    pointerByIndex.set(idx, list);
  });
  const pointerNames = new Set(Object.keys(frame.pointers));
  const scalarEntries = Object.entries(frame.variables).filter(
    ([name]) => !pointerNames.has(name)
  );

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto p-4">
      {/* Active Variables */}
      <section>
        <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-paper/40">
          Active Variables
        </h3>
        {scalarEntries.length === 0 ? (
          <p className="text-xs text-paper/30">(none yet)</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {scalarEntries.map(([name, value]) => (
              <div
                key={name}
                className="rounded-md border border-ink-600 bg-ink-800 px-2.5 py-1.5 font-mono text-xs"
              >
                <span className="text-node-call">{name}</span>
                <span className="text-paper/40"> : </span>
                <span className="text-paper/90">{String(value)}</span>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Array / Pointer visualizer */}
      <section>
        <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-paper/40">
          {frame.arrayName ? `Array: ${frame.arrayName}` : "Array / List"}
        </h3>
        {frame.arrayState.length === 0 ? (
          <p className="text-xs text-paper/30">(no array/list in scope)</p>
        ) : (
          <div className="flex items-end gap-1 overflow-x-auto pb-1">
            {frame.arrayState.map((value, i) => {
              const tags = pointerByIndex.get(i) ?? [];
              return (
                <div key={i} className="flex flex-col items-center gap-1">
                  <div className="flex h-5 flex-wrap items-center justify-center gap-0.5">
                    {tags.map((tag) => (
                      <span
                        key={tag}
                        className="rounded bg-node-loop px-1 text-[10px] font-semibold text-ink-950"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                  <div
                    className={`flex h-12 w-12 items-center justify-center rounded-md border font-mono text-sm ${
                      tags.length > 0
                        ? "border-node-loop bg-node-loop/15 text-paper"
                        : "border-ink-600 bg-ink-800 text-paper/80"
                    }`}
                  >
                    {String(value)}
                  </div>
                  <span className="text-[10px] text-paper/30">{i}</span>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* Call Stack */}
      <section>
        <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-paper/40">
          Call Stack
        </h3>
        <div className="flex flex-col-reverse gap-1">
          {[...frame.callStack].reverse().map((fn, i) => (
            <div
              key={`${fn}-${i}`}
              className={`rounded-md border px-2.5 py-1 font-mono text-xs ${
                i === 0
                  ? "border-node-function bg-node-function/15 text-paper"
                  : "border-ink-600 bg-ink-800 text-paper/60"
              }`}
            >
              {fn}()
            </div>
          ))}
        </div>
      </section>

      {/* Execution Controls */}
      <div className="mt-auto flex items-center gap-3 border-t border-ink-700 pt-3">
        <button
          onClick={() => setIndex((i) => Math.max(0, i - 1))}
          disabled={index === 0}
          className="rounded-md border border-ink-600 p-1.5 text-paper/70 hover:bg-ink-800 disabled:opacity-30"
          aria-label="Step previous"
        >
          <SkipBack className="h-4 w-4" />
        </button>
        <button
          onClick={() => setIsPlaying((p) => !p)}
          className="rounded-md bg-signal p-1.5 text-ink-950 hover:bg-signal/90"
          aria-label={isPlaying ? "Pause" : "Play"}
        >
          {isPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
        </button>
        <button
          onClick={() => setIndex((i) => Math.min(frames.length - 1, i + 1))}
          disabled={index >= frames.length - 1}
          className="rounded-md border border-ink-600 p-1.5 text-paper/70 hover:bg-ink-800 disabled:opacity-30"
          aria-label="Step next"
        >
          <SkipForward className="h-4 w-4" />
        </button>

        <input
          type="range"
          min={0}
          max={frames.length - 1}
          value={index}
          onChange={(e) => setIndex(Number(e.target.value))}
          className="mx-2 flex-1 accent-signal"
        />
        <span className="w-16 shrink-0 font-mono text-xs text-paper/50">
          {index + 1}/{frames.length}
        </span>

        <label className="flex items-center gap-1.5 text-xs text-paper/40">
          Speed
          <input
            type="range"
            min={100}
            max={1500}
            step={100}
            value={1600 - speedMs}
            onChange={(e) => setSpeedMs(1600 - Number(e.target.value))}
            className="w-16 accent-signal"
          />
        </label>
      </div>

      <p className="font-mono text-[11px] text-paper/30">
        line {frame.activeLine} · step {frame.step} · {frame.event}
      </p>
    </div>
  );
}
