"use client";
import {recoveryHint} from './recovery';

/** "What happened / What to do next" under an error message. Renders nothing when unknown. */
export function RecoveryHint({error}){
  const hint=recoveryHint(error);
  if(!hint)return null;
  return <div className="recovery-hint" role="note" aria-label="How to recover">
    <p><strong>What happened:</strong> {hint.what}</p>
    <p><strong>What to do next:</strong> {hint.next}</p>
  </div>;
}
