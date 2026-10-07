/** Interactive Tool-Call DAG and cycle visualization component. */

import React from 'react';
import { DAGNode, TraceDAG } from '../types';

interface DAGVisualizerProps {
  dag: TraceDAG;
  selectedNodeId: string | null;
  onSelectNode: (nodeId: string) => void;
}

export const DAGVisualizer: React.FC<DAGVisualizerProps> = ({ dag, selectedNodeId, onSelectNode }) => {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg">
      <div className="flex flex-wrap items-center justify-between gap-4 mb-4 pb-3 border-b border-slate-800">
        <div>
          <h3 className="text-base font-semibold text-slate-100 flex items-center gap-2">
            Tool-Call Execution DAG
            {dag.has_cycles && (
              <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/20">
                Cycle / Retry Loop Detected
              </span>
            )}
          </h3>
          <p className="text-xs text-slate-400 mt-1">
            Deterministic dependency graph with cycle detection and critical path latency.
          </p>
        </div>

        <div className="flex items-center gap-3 text-xs text-slate-400">
          <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-emerald-500 inline-block"/> Success</span>
          <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-rose-500 inline-block"/> Error</span>
          <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-amber-500 inline-block"/> Retrying</span>
          <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded border border-amber-400 inline-block"/> Critical Path</span>
        </div>
      </div>

      {dag.nodes.length === 0 ? (
        <div className="text-center py-10 text-slate-500 text-sm">No spans recorded in this trace DAG.</div>
      ) : (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {dag.nodes.map((node: DAGNode) => {
              const selected = selectedNodeId === node.id;
              const inCycle = dag.cycle_nodes.includes(node.id);
              const inCrit = dag.critical_path.includes(node.id);
              const sColor = node.status === 'success' ? (inCrit ? 'border-amber-400' : 'border-emerald-500/40') : node.status === 'error' ? 'border-rose-500' : 'border-amber-500/50';
              const bColor = node.status === 'success' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : node.status === 'error' ? 'bg-rose-500/10 text-rose-400 border-rose-500/20' : 'bg-amber-500/10 text-amber-400 border-amber-500/20';

              return (
                <div
                  key={node.id}
                  onClick={() => onSelectNode(node.id)}
                  className={`p-3.5 rounded-lg border cursor-pointer transition hover:bg-slate-800 bg-slate-800/60 ${selected ? 'border-indigo-500 ring-2 ring-indigo-500/30' : sColor}`}
                >
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <span className="font-mono text-xs text-indigo-300 truncate font-semibold" title={node.label}>{node.label}</span>
                    <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium border ${bColor}`}>{node.status}</span>
                  </div>
                  <div className="flex items-center justify-between text-[11px] text-slate-400 mb-1">
                    <span className="capitalize">{node.span_type.replace('_', ' ')}</span>
                    <span className="font-mono text-slate-300">{node.latency_ms.toFixed(1)} ms</span>
                  </div>
                  <div className="flex items-center justify-between text-[11px] text-slate-500">
                    <span>Step {node.step_index + 1}</span>
                    <span className="font-mono text-emerald-400/80">${node.cost_usd.toFixed(5)}</span>
                  </div>
                  {inCycle && <div className="mt-2 text-[10px] text-rose-400 bg-rose-950/40 px-2 py-0.5 rounded border border-rose-900/40">⚠️ Cyclic tool oscillation</div>}
                  {inCrit && <div className="mt-1 text-[10px] text-amber-400/90">⏱️ Critical Path ({dag.critical_path_latency_ms.toFixed(0)} ms total)</div>}
                </div>
              );
            })}
          </div>

          <div className="bg-slate-950/60 rounded-lg p-3 border border-slate-800/80 text-xs flex flex-wrap gap-x-6 gap-y-2 text-slate-400">
            <div>Fan-Outs: <span className="font-mono text-slate-200">{dag.parallel_fan_outs}</span></div>
            <div>Retry Loops: <span className="font-mono text-rose-400">{dag.retry_loops_detected}</span></div>
            <div>Critical Path: <span className="font-mono text-amber-300">{dag.critical_path_latency_ms.toFixed(1)} ms</span></div>
          </div>
        </div>
      )}
    </div>
  );
};
