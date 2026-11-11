# Studio 3.4 preview: a playable, file-based video editor

This branch replaces the old FFmpeg settings form with a PySide6 editor that
works with actual local video files. It is not a multi-track NLE.

## Editor workflow

1. Open Studio chỉnh sửa, choose + Nhập video, select MP4/MOV/MKV/M4V/WebM.
2. Select a clip and play it using the native Qt Multimedia widget, pause,
   scrub, set IN and OUT points, then choose an output aspect ratio.
3. Khung & màu offers 9:16, 16:9, square, crop/pad/blur, brightness,
   contrast, saturation and trim.
4. Che phụ đề extracts a current FFmpeg frame and allows mouse-drawn masks.
   Optional Chinese OCR examines that chosen frame, not the whole film.
5. Chữ & âm thanh offers optional CTA, source URL, SRT and narration.
   Blank CTA/source fields do NOT fabricate promotion or Douyin attribution.
6. Xuất MP4 chooses the destination and checks rights. Export current clip
   or all selected clips; every MP4 is verified with FFprobe and never
   overwrites any source or pre-existing render.
7. Xem thử bản dựng 5 giây renders a real preview including the selected
   trim, colors, masks and overlays, then plays it. Use Clip gốc to return.

## Constraints

- A batch applies the same trim and masks to all clips. Verify each clip.
- Qt Multimedia requires appropriate Windows media codecs. If playback is
  unavailable, FFmpeg frame extraction and export remain available.
- OCR checks only a selected frame, not moving captions over full duration.
- No access control bypass or claim that crop/color removes copyright.
- Exports H.264 video and AAC for available audio.

## Validation gates

- Unit tests for duration, no-clobber, preview length, and empty overlay.
- A real synthetic MP4 edited/trimmed and exported via FFmpeg/FFprobe.
- Frozen EXE --render-self-test additionally renders a 5-second-or-less
  preview of a synthetic MP4.
- Frozen EXE --ui-smoke-test constructs all editor inspector tabs.
- Windows PyInstaller explicitly bundles Qt Multimedia.

## Manual acceptance

On a Windows PC, open an authorized real MP4, play with audio, seek, mark
in/out, draw blur, render preview, export MP4 and verify the output.
Repeat with multiple source videos. Automated CI cannot replace interactive
testing of the entire media subsystem.
