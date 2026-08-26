import React, { useEffect, useState } from "react";

export default function ProductImage({ src, alt, className = "" }) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [src]);
  if (!src || failed) {
    return <div className={`image-fallback ${className}`}>图片暂不可用</div>;
  }
  return (
    <img
      alt={alt}
      className={className}
      loading="lazy"
      onError={() => setFailed(true)}
      referrerPolicy="no-referrer"
      src={src}
    />
  );
}
