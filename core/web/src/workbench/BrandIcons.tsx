import util0 from "./assets/utility-refresh.svg";
import util1 from "./assets/utility-external.svg";
import util2 from "./assets/utility-external.svg";
import util3 from "./assets/utility-close.svg";
import util4 from "./assets/utility-chevron-right.svg";
import util5 from "./assets/utility-chevron-down.svg";
import util6 from "./assets/utility-arrow-right.svg";
import util7 from "./assets/utility-download.svg";
import util8 from "./assets/utility-download.svg";
import util9 from "./assets/utility-filter.svg";
import util10 from "./assets/utility-settings.svg";
import util11 from "./assets/utility-settings.svg";
import util12 from "./assets/utility-info.svg";
import util13 from "./assets/utility-logout.svg";
import util14 from "./assets/utility-check.svg";
import util15 from "./assets/utility-table.svg";
import util16 from "./assets/utility-file.svg";
import util17 from "./assets/utility-shield.svg";
import util18 from "./assets/utility-send.svg";
import util19 from "./assets/utility-message.svg";
import util20 from "./assets/utility-network.svg";
import util21 from "./assets/utility-activity.svg";
import util22 from "./assets/utility-zoom-in.svg";
import util23 from "./assets/utility-zoom-out.svg";
import React from "react";
import workspace from "./assets/workspace.svg";
import globe from "./assets/globe.svg";
import database from "./assets/database.svg";
import search from "./assets/search.svg";
import help from "./assets/help.svg";
import book from "./assets/book.svg";
import upload from "./assets/upload.svg";
import compare from "./assets/compare.svg";
import bookmark from "./assets/bookmark.svg";
import sun from "./assets/sun.svg";
import moon from "./assets/moon.svg";
function icon(asset: string) {
  return function BrandIcon({
    size = 20,
    className = "",
  }: {
    size?: number;
    className?: string;
  }) {
    return (
      <span
        aria-hidden="true"
        className={`wb-custom-icon ${className}`}
        style={{
          width: size,
          height: size,
          maskImage: `url(${asset})`,
          WebkitMaskImage: `url(${asset})`,
        }}
      />
    );
  };
}
export const Layers = icon(workspace),
  Globe2 = icon(globe),
  Database = icon(database),
  Search = icon(search),
  HelpCircle = icon(help),
  BookOpen = icon(book),
  Upload = icon(upload),
  Code2 = icon(compare),
  Bookmark = icon(bookmark),
  Sun = icon(sun),
  Moon = icon(moon);

export const RotateCcw = icon(util0);
export const ExternalLink = icon(util1);
export const ArrowUpRight = icon(util2);
export const X = icon(util3);
export const ChevronRight = icon(util4);
export const ChevronDown = icon(util5);
export const ArrowRight = icon(util6);
export const Download = icon(util7);
export const ArrowDownToLine = icon(util8);
export const Filter = icon(util9);
export const Settings2 = icon(util10);
export const SlidersHorizontal = icon(util11);
export const Info = icon(util12);
export const LogOut = icon(util13);
export const CheckCircle2 = icon(util14);
export const Table2 = icon(util15);
export const FileText = icon(util16);
export const ShieldCheck = icon(util17);
export const Send = icon(util18);
export const MessageSquare = icon(util19);
export const Network = icon(util20);
export const Activity = icon(util21);
export const ZoomIn = icon(util22);
export const ZoomOut = icon(util23);
