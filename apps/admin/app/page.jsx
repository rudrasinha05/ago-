import {WorkspaceShell} from '@ago/ui';
import {capabilities} from '@ago/shared';
export default function Page() {return <WorkspaceShell title="AGO Administration" description="An operational foundation for tenant and governance administration." kind="admin" capabilities={capabilities} />;}
