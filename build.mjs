import {cpSync,rmSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {resolve,dirname,basename,join} from 'node:path';
const root=fileURLToPath(new URL('.',import.meta.url));
const output=resolve(root,'dist');
if(dirname(output)!==resolve(root)||basename(output)!=='dist')throw new Error('Destino de build inválido');
rmSync(output,{recursive:true,force:true});
cpSync(join(root,'public'),output,{recursive:true});
console.log('Demonstração pronta em dist/');
