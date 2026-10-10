import type {HealthResponse} from '@ago/shared';
export declare class AgoReadClient {
  constructor(baseUrl: string, fetcher?: typeof fetch);
  readonly origin: string;
  readonly apiVersion: 'v1';
  health(options?: {timeoutMs?: number}): Promise<HealthResponse>;
}
