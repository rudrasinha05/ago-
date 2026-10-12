export type IntegrationScope = 'events:read'|'tasks:read'|'tasks:propose'|'analytics:read';
export interface TaskSummary {id:string;status:'proposed'|'waiting_approval'|'ready'|'running'|'completed'|'failed';assignee_id:string;created_at:string;updated_at:string;}
export interface ProposedTask {id:string;tenant_id:string;action:string;assignee_id:string;status:'proposed';approval_id:null;dna_context:null;experiment_context:null;}
export interface IntegrationEvent {sequence:number;id:string;event_type:string;payload:Record<string,unknown>;created_at:string;}
export interface StreamEvent {id:number;event:string;data:Record<string,unknown>;}
export class CompanyAPI {
 constructor(origin:string,token:string,options?:{fetcher?:typeof fetch;retries?:number});
 request<T=Record<string,unknown>>(path:string,options?:{method?:string;body?:unknown;idempotencyKey?:string;signal?:AbortSignal}):Promise<T>;
 events(after?:number,limit?:number):Promise<{events:IntegrationEvent[];next_cursor:number;schema_version:1}>;
 tasks(after?:string,limit?:number):Promise<{tasks:TaskSummary[];next_cursor:string|null}>;
 proposeTask(action:string,assigneeId:string,idempotencyKey:string):Promise<ProposedTask>;
 stream(after?:number,options?:{signal?:AbortSignal}):AsyncGenerator<StreamEvent>;
}
