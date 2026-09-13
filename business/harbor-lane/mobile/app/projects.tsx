import { useEffect, useState } from "react";
import { ActivityIndicator, FlatList, StyleSheet, Text, View } from "react-native";
import { supabase } from "../lib/supabase";

interface Project {
  id: string;
  name: string;
  status: string;
  project_type: string;
}

export default function ProjectsScreen() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      const { data, error: err } = await supabase.from("projects").select("id, name, status, project_type");
      if (err) setError("Sign in to view your projects.");
      else setProjects(data ?? []);
      setLoading(false);
    })();
  }, []);

  if (loading) return <ActivityIndicator style={{ flex: 1 }} color="#2d6d87" />;

  return (
    <View style={styles.container}>
      {error && <Text style={styles.error}>{error}</Text>}
      <FlatList
        data={projects}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <View style={styles.card}>
            <Text style={styles.name}>{item.name}</Text>
            <Text style={styles.meta}>
              {item.project_type} · {item.status}
            </Text>
          </View>
        )}
        ListEmptyComponent={<Text style={styles.empty}>No projects</Text>}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#fafbfc", padding: 16 },
  card: {
    backgroundColor: "#fff",
    borderRadius: 10,
    padding: 14,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: "#e2e8f0",
  },
  name: { fontSize: 15, fontWeight: "600" },
  meta: { marginTop: 4, fontSize: 12, color: "#64748b", textTransform: "capitalize" },
  error: { color: "#b45309", marginBottom: 12, fontSize: 13 },
  empty: { textAlign: "center", color: "#94a3b8", marginTop: 40 },
});
