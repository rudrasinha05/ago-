import '@ago/ui/workspace.css';
import './workspace.css';
import {SessionProvider} from '../components/session';
export const metadata = {title: 'AGO Workspace', description: 'Your organization, with clear authority and evidence.'};
export default function Layout({children}) {return <html lang="en"><body><SessionProvider>{children}</SessionProvider></body></html>;}
