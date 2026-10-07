import { useEffect, useRef, useState } from "react";
import { Layers3, MapPinned, MessageSquareText, Search } from "lucide-react";
import Map from "ol/Map.js";
import View from "ol/View.js";
import TileLayer from "ol/layer/Tile.js";
import { unByKey } from "ol/Observable.js";
import { fromLonLat } from "ol/proj.js";
import ImageTile from "ol/source/ImageTile.js";
import "ol/ol.css";

import { useTranslation } from "@/i18n";

type MapStatus = "unconfigured" | "loading" | "ready" | "error";

function tileUrl(layer: "img" | "cia", key: string) {
  return (
    "https://t0.tianditu.gov.cn/" +
    layer +
    "_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=" +
    layer +
    "&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&tk=" +
    encodeURIComponent(key)
  );
}

export default function MapPage() {
  const { t } = useTranslation();
  const tiandituKey = import.meta.env.VITE_TIANDITU_TK?.trim();
  const mapElement = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<MapStatus>(
    tiandituKey ? "loading" : "unconfigured",
  );

  useEffect(() => {
    if (!tiandituKey || !mapElement.current) return;

    const imagery = new ImageTile({
      url: tileUrl("img", tiandituKey),
      attributions: '<a href="https://www.tianditu.gov.cn/">© 天地图</a>',
    });
    const map = new Map({
      target: mapElement.current,
      layers: [
        new TileLayer({ source: imagery }),
        new TileLayer({
          source: new ImageTile({ url: tileUrl("cia", tiandituKey) }),
        }),
      ],
      view: new View({
        center: fromLonLat([113.58, 22.95]),
        zoom: 9,
        minZoom: 3,
        maxZoom: 18,
      }),
    });
    let hasLoadedTile = false;
    const loadKey = imagery.on("tileloadend", () => {
      hasLoadedTile = true;
      setStatus("ready");
    });
    const errorKey = imagery.on("tileloaderror", () => {
      if (!hasLoadedTile) setStatus("error");
    });

    return () => {
      unByKey([loadKey, errorKey]);
      map.setTarget(undefined);
      map.dispose();
    };
  }, [tiandituKey]);

  const mapMessage =
    status === "unconfigured"
      ? t("TianDiTu key is not configured")
      : status === "error"
        ? t("Map tiles could not be loaded")
        : t("Loading map");

  return (
    <main
      className="flex h-full min-h-0 flex-col overflow-y-auto bg-background text-foreground xl:flex-row xl:overflow-hidden"
      aria-label={t("Map")}
    >
      <section
        className="relative min-h-[52vh] flex-1 overflow-hidden bg-muted xl:min-h-0"
        aria-label={t("Map canvas")}
      >
        <div ref={mapElement} className="absolute inset-0" />
        {status !== "ready" && (
          <div className="absolute inset-0 z-10 grid place-items-center bg-muted px-6 text-center">
            <div className="grid justify-items-center gap-3">
              <MapPinned className="size-9 text-muted-foreground" aria-hidden />
              <p role={status === "error" ? "alert" : "status"} className="m-0 text-sm font-medium">
                {mapMessage}
              </p>
              {status === "error" && (
                <p className="m-0 text-sm text-muted-foreground">
                  {t("Check the key and allowed origin, then reload")}
                </p>
              )}
              {status === "unconfigured" && (
                <p className="m-0 text-sm text-muted-foreground">
                  {t("Set VITE_TIANDITU_TK in web/.env.local")}
                </p>
              )}
            </div>
          </div>
        )}
        {status === "ready" && (
          <div className="pointer-events-none absolute top-4 left-4 z-10 inline-flex items-center gap-2 rounded-md border border-border bg-background/95 px-3 py-2 text-sm font-medium shadow-sm">
            <Layers3 className="size-4" aria-hidden />
            {t("Map")}
          </div>
        )}
      </section>

      <aside className="flex min-h-[18rem] w-full shrink-0 flex-col border-t border-border bg-background xl:min-h-0 xl:w-[22rem] xl:border-t-0 xl:border-l">
        <div className="border-b border-border px-5 py-4">
          <h1 className="m-0 text-base font-semibold">{t("Image search")}</h1>
        </div>
        <div className="grid flex-1 place-items-center p-6 text-center">
          <div className="grid justify-items-center gap-3">
            <Search className="size-7 text-muted-foreground" aria-hidden />
            <p className="m-0 text-sm text-muted-foreground">
              {t("Catalog search is not connected")}
            </p>
          </div>
        </div>
        <div className="border-t border-border p-5">
          <div className="flex items-center gap-2 text-sm font-medium">
            <MessageSquareText className="size-4" aria-hidden />
            {t("Map conversation")}
          </div>
          <p className="m-0 mt-3 text-sm text-muted-foreground">
            {t("Map conversation is not connected")}
          </p>
        </div>
      </aside>
    </main>
  );
}
