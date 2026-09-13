import { useEffect, useState } from "react";
import { ActivityIndicator, FlatList, StyleSheet, Text, View } from "react-native";
import { supabase } from "../lib/supabase";

interface Invoice {
  id: string;
  invoice_number: string;
  status: string;
  total_gbp: number;
  due_date: string;
}

function formatGbp(n: number) {
  return `£${n.toFixed(2)}`;
}

export default function InvoicesScreen() {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      const { data, error: err } = await supabase
        .from("invoices")
        .select("id, invoice_number, status, total_gbp, due_date");
      if (err) setError("Sign in to view invoices.");
      else setInvoices(data ?? []);
      setLoading(false);
    })();
  }, []);

  if (loading) return <ActivityIndicator style={{ flex: 1 }} color="#2d6d87" />;

  return (
    <View style={styles.container}>
      {error && <Text style={styles.error}>{error}</Text>}
      <FlatList
        data={invoices}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <View style={styles.card}>
            <View style={styles.row}>
              <Text style={styles.number}>{item.invoice_number}</Text>
              <Text style={styles.total}>{formatGbp(item.total_gbp)}</Text>
            </View>
            <Text style={styles.meta}>
              Due {item.due_date} · {item.status}
            </Text>
          </View>
        )}
        ListEmptyComponent={<Text style={styles.empty}>No invoices</Text>}
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
  row: { flexDirection: "row", justifyContent: "space-between" },
  number: { fontSize: 15, fontWeight: "600" },
  total: { fontSize: 15, fontWeight: "600", color: "#2d6d87" },
  meta: { marginTop: 4, fontSize: 12, color: "#64748b", textTransform: "capitalize" },
  error: { color: "#b45309", marginBottom: 12, fontSize: 13 },
  empty: { textAlign: "center", color: "#94a3b8", marginTop: 40 },
});
