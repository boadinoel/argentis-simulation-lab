<template>
  <main class="knowledge-page">
    <nav><router-link to="/">← All projects</router-link></nav>
    <h1>{{ project?.name || 'Research workspace' }}</h1>
    <p>Keep this topic's research growing in one graph. Use a separate project for an unrelated topic.</p>
    <p v-if="error" role="alert" class="error">{{ error }}</p>
    <p v-if="notice" role="status">{{ notice }}</p>
    <section v-if="project">
      <h2>Current research · Revision {{ knowledge.revision }}</h2>
      <p>{{ project.files?.length || 0 }} document(s). <router-link :to="'/process/'+project.project_id">Explore graph</router-link></p>
      <small>Graph {{ project.graph_id }} · Project {{ project.project_id }}</small>
      <p>Research updates keep this graph ID. Saved runs, reports and interviews remain separate. Simulated opinions are not automatically added as source facts.</p>
    </section>
    <section>
      <h2>Add research to this graph</h2>
      <p>Upload new evidence or a clearly dated correction. Original documents stay preserved. Graph extraction uses your configured API services.</p>
      <form @submit.prevent="upload">
        <label>Update title<input v-model="title" required maxlength="200" placeholder="e.g. November strategy and customer updates" /></label>
        <label>Source date (optional)<input v-model="sourceDate" type="date" /></label>
        <label>New documents<input ref="fileInput" type="file" multiple accept=".pdf,.md,.txt,.markdown" required @change="files=Array.from($event.target.files)" /></label>
        <label>Source or correction notes (optional)<textarea v-model="note" maxlength="5000" placeholder="What changed? If correcting an earlier claim, identify it and explain the correction." /></label>
        <button :disabled="working || blocked || !project?.graph_id">{{ working ? 'Submitting…' : 'Add research to existing graph' }}</button>
      </form>
      <p v-if="blocked">An update is unfinished. Review its status below before adding more research or preparing new scenarios.</p>
    </section>
    <section>
      <h2>New scenario using this research</h2>
      <p>This creates a separate simulation using revision {{ knowledge.revision }}. It does not run models or alter prior simulations. Agent preparation and simulation start are separate actions.</p>
      <form @submit.prevent="createScenario">
        <label>Scenario objective<textarea v-model="objective" required placeholder="Who should respond, what decision should they debate, and what would challenge your assumptions?" /></label>
        <button :disabled="working || blocked || !project?.graph_id">Create scenario</button>
      </form>
    </section>
    <section>
      <h2>Research history</h2>
      <p v-if="!knowledge.updates.length">Original research · Revision 1. No updates yet.</p>
      <article v-for="u in [...knowledge.updates].reverse()" :key="u.update_id" :data-update-id="u.update_id">
        <h3>{{ u.title }}</h3><p>{{ u.status.replaceAll('_',' ') }} <span v-if="u.revision">· Revision {{ u.revision }}</span></p>
        <p>{{ u.message }}</p><small>Added {{ u.created_at }} <span v-if="u.source_date">· Source date {{ u.source_date }}</span></small>
        <ul><li v-for="f in u.files" :key="f.sha256">{{ f.filename }}</li></ul>
        <button v-if="u.status !== 'completed'" :disabled="working" @click="resume(u)">Check / resume recorded update</button>
      </article>
    </section>
    <section>
      <h2>Saved scenarios and results</h2>
      <p v-if="!simulations.length">No scenarios yet.</p>
      <article v-for="sim in simulations" :key="sim.simulation_id">
        <router-link :to="'/simulation/'+sim.simulation_id+'/start'">{{ sim.simulation_id }} · {{ sim.runner_status }} · {{ sim.current_round }}/{{ sim.total_rounds }} rounds</router-link>
        <p v-if="sim.report_id"><router-link :to="'/report/'+sim.report_id">Read report</router-link> · <router-link :to="'/interaction/'+sim.report_id">Interview agents</router-link></p>
      </article>
    </section>
  </main>
</template>

<script setup>
import {ref,computed,onMounted,onUnmounted} from 'vue'
import {useRoute,useRouter} from 'vue-router'
import api from '../api/index'
const route=useRoute(),router=useRouter(),pid=route.params.projectId
const project=ref(null),knowledge=ref({revision:1,updates:[]}),simulations=ref([])
const error=ref(''),notice=ref(''),working=ref(false),title=ref(''),sourceDate=ref(''),note=ref(''),objective=ref(''),files=ref([]),fileInput=ref(null)
const blocked=computed(()=>knowledge.value.updates.some(u=>u.status!=='completed'))
let timer
async function load(){
  try{
    const [p,k,s]=await Promise.all([api.get('/api/graph/project/'+pid),api.get('/api/graph/project/'+pid+'/knowledge'),api.get('/api/simulation/history?limit=200')])
    project.value=p.data;knowledge.value=k.data;simulations.value=s.data.filter(s=>s.project_id===pid)
  }catch(e){error.value=e.message}
}
async function upload(){
  working.value=true;error.value='';notice.value=''
  try{
    const data=new FormData();data.append('title',title.value);data.append('source_date',sourceDate.value);data.append('note',note.value)
    files.value.forEach(f=>data.append('files',f))
    const r=await api.post('/api/graph/project/'+pid+'/knowledge',data,{headers:{'Content-Type':'multipart/form-data'}})
    knowledge.value=r.data;notice.value=r.data.reused?'This upload already has a recorded update. No duplicate was submitted.':'Research update submitted. You can leave and return while it processes.'
    files.value=[];if(fileInput.value)fileInput.value.value=''
  }catch(e){error.value=e.message}finally{working.value=false}
}
async function resume(u){
  working.value=true;error.value=''
  try{await api.post('/api/graph/project/'+pid+'/knowledge/'+u.update_id+'/resume');await load()}
  catch(e){error.value=e.message}finally{working.value=false}
}
async function createScenario(){
  working.value=true;error.value=''
  try{
    const r=await api.post('/api/simulation/create',{project_id:pid,graph_id:project.value.graph_id,simulation_requirement:objective.value,enable_reddit:true,enable_twitter:false})
    await router.push('/simulation/'+r.data.simulation_id)
  }catch(e){error.value=e.message}finally{working.value=false}
}
onMounted(async()=>{await load();timer=setInterval(load,4000)})
onUnmounted(()=>clearInterval(timer))
</script>

<style scoped>
.knowledge-page{max-width:850px;margin:auto;padding:24px;color:#17202b;font:16px/1.55 system-ui;background:#fafafa;min-height:100vh;overflow-wrap:anywhere}
section{background:white;border:1px solid #ddd;border-radius:12px;padding:22px;margin:22px 0}
h1{font-size:28px;line-height:1.2}h2{font-size:21px}h3{font-size:18px}label{display:block;margin:16px 0;font-weight:600}
input,textarea{display:block;width:100%;box-sizing:border-box;padding:12px;margin-top:6px;border:1px solid #aaa;border-radius:6px;font:inherit}textarea{min-height:110px}
button{padding:13px 18px;background:#17202b;color:white;border:0;border-radius:6px;font:inherit;cursor:pointer}button:disabled{opacity:.5;cursor:default}
article{border-top:1px solid #ddd;padding:16px 0}a{color:#a53511}small{color:#58616d}.error{color:#a31414}
@media(max-width:600px){.knowledge-page{padding:16px}section{padding:16px}h1{font-size:25px}}
</style>
