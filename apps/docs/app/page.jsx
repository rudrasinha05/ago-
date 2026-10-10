import {WorkspaceShell} from '@ago/ui';
import {capabilities} from '@ago/shared';
export default function Page() {return <WorkspaceShell title="AGO Architecture" description="A shared map of the system, its boundaries and verified capabilities." kind="docs" capabilities={capabilities} />;}
