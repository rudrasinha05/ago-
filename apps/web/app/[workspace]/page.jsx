import {Workspace} from '../../components/workspace';
export function generateStaticParams() {return ['strategy','governance','organization','knowledge','tools','calendar','twin'].map(workspace=>({workspace}));}
export const dynamicParams = false;
export default async function Page({params}) {const {workspace} = await params; return <Workspace page={workspace} />;}
