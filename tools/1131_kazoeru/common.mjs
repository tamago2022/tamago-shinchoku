import * as B from './bundle.mjs';
export const {CG,SP,SIG}=B;
export const artists=CG.artists;
export const byId=new Map(artists.map(a=>[a.id,a]));
export const songs=[]; for(const a of artists) for(const s of (a.songs||[])) songs.push({a,s});
export const norm=t=>(t||'').toLowerCase().replace(/\(.*?\)|\[.*?\]|（.*?）/g,'')
 .replace(/\s*(live|official|mv|music video|cover|カバー|feat\..*|ft\..*)\s*/g,'')
 .replace(/[^a-z0-9぀-ヿ一-龯]/g,'').trim();
export const ERA_YEARS=15;
