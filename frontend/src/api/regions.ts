export type RegionOption = {
  id: string;
  label: string;
  lat: number;
  lon: number;
};

export async function fetchRegions(): Promise<RegionOption[]> {
  const res = await fetch("/api/regions");
  if (!res.ok) {
    throw new Error(`Error al cargar regiones (${res.status})`);
  }
  return res.json();
}
