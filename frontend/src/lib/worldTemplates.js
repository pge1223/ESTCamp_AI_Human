const KEY = 'world_templates';

export function getTemplates() {
  try {
    return JSON.parse(localStorage.getItem(KEY) || '[]');
  } catch { return []; }
}

export function saveTemplate({ title, genre, setting, description, rules, characters }) {
  const templates = getTemplates();
  const template = {
    id: `tmpl_${Date.now()}`,
    saved_at: new Date().toISOString(),
    title, genre, setting, description, rules,
    characters: (characters || []).map(c => ({
      name: c.name ?? '',
      role: c.role ?? 'supporting',
      personality: c.personality ?? '',
      prompt: c.prompt ?? '',
      address_rules: c.address_rules ?? [],
    })),
  };
  templates.unshift(template);
  localStorage.setItem(KEY, JSON.stringify(templates));
  return template;
}

export function deleteTemplate(id) {
  const updated = getTemplates().filter(t => t.id !== id);
  localStorage.setItem(KEY, JSON.stringify(updated));
}
