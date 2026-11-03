<template>
  <section class="workspace" aria-label="Saved projects">
    <h2>Your research projects</h2>
    <p>Each project keeps its own graph and research. Simulations and reports stay with their project.</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <article v-for="project in projects" :key="project.project_id">
      <h3><router-link :to="'/process/' + project.project_id">{{ project.name }}</router-link></h3>
      <p>{{ project.status.replaceAll('_', ' ') }} · {{ project.files?.length || 0 }} document(s)</p>
      <small>Project {{ project.project_id }} · Graph {{ project.graph_id || 'not built yet' }}</small>
      <div v-for="sim in simulations.filter(s => s.project_id === project.project_id)" :key="sim.simulation_id">
        <router-link :to="'/simulation/' + sim.simulation_id + '/start'">Open simulation · {{ sim.runner_status }} · {{ sim.current_round }}/{{ sim.total_rounds }} rounds</router-link>
        <router-link v-if="sim.report_id" :to="'/report/' + sim.report_id"> · Report</router-link>
        <router-link v-if="sim.report_id" :to="'/interaction/' + sim.report_id"> · Interview agents</router-link>
      </div>
    </article>
    <p v-if="loaded && projects.length === 0">No projects yet. Name a project and upload its reports above.</p>
  </section>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api/index'
const projects = ref([]), simulations = ref([]), error = ref(''), loaded = ref(false)
onMounted(async () => {
  try {
    const [p, s] = await Promise.all([api.get('/api/graph/project/list?limit=200'), api.get('/api/simulation/history?limit=200')])
    projects.value = p.data
    simulations.value = s.data
  } catch (err) { error.value = 'Cannot load saved projects: ' + err.message }
  finally { loaded.value = true }
})
</script>

<style scoped>
.workspace { padding: 28px; max-width: 1200px; margin: auto; }
article { border: 1px solid #ddd; border-radius: 10px; padding: 18px; margin: 16px 0; overflow-wrap: anywhere; }
article div { margin-top: 12px; }
a { color: #b53510; }
small { color: #666; }
</style>
