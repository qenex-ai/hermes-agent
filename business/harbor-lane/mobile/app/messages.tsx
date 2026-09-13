import { useEffect, useState } from "react";
import { ActivityIndicator, FlatList, StyleSheet, Text, View } from "react-native";
import { supabase } from "../lib/supabase";

interface Message {
  id: string;
  subject: string;
  body: string;
  is_from_client: boolean;
  created_at: string;
}

export default function MessagesScreen() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      const { data, error: err } = await supabase
        .from("messages")
        .select("id, subject, body, is_from_client, created_at")
        .order("created_at", { ascending: false });
      if (err) setError("Sign in to view messages.");
      else setMessages(data ?? []);
      setLoading(false);
    })();
  }, []);

  if (loading) return <ActivityIndicator style={{ flex: 1 }} color="#2d6d87" />;

  return (
    <View style={styles.container}>
      {error && <Text style={styles.error}>{error}</Text>}
      <FlatList
        data={messages}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <View style={styles.card}>
            <Text style={styles.subject}>{item.subject}</Text>
            <Text style={styles.body} numberOfLines={3}>
              {item.body}
            </Text>
            <Text style={styles.meta}>
              {item.is_from_client ? "From you" : "From Harbor Lane"} ·{" "}
              {new Date(item.created_at).toLocaleDateString("en-GB")}
            </Text>
          </View>
        )}
        ListEmptyComponent={<Text style={styles.empty}>No messages</Text>}
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
  subject: { fontSize: 15, fontWeight: "600" },
  body: { marginTop: 6, fontSize: 13, color: "#475569" },
  meta: { marginTop: 8, fontSize: 11, color: "#94a3b8" },
  error: { color: "#b45309", marginBottom: 12, fontSize: 13 },
  empty: { textAlign: "center", color: "#94a3b8", marginTop: 40 },
});
