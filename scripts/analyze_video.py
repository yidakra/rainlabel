import os
import json
from pathlib import Path
from google.cloud import videointelligence_v1 as videointelligence

# Optional import; only needed when uploading to GCS
try:
    from google.cloud import storage as gcs_storage
except Exception:
    gcs_storage = None

# Resolve project root and videos directory; allow env override
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VIDEOS = (PROJECT_ROOT / "videos").as_posix()
VIDEO_DIR = os.environ.get("VIDEO_DIR", DEFAULT_VIDEOS)

_CLIENT = None
_STORAGE_CLIENT = None

def get_client():
    """Lazily initialize the Video Intelligence client.

    Defers auth and any subprocess calls until needed, and allows
    KeyboardInterrupt to gracefully abort without a long traceback.
    """
    global _CLIENT
    if _CLIENT is None:
        try:
            _CLIENT = videointelligence.VideoIntelligenceServiceClient()
        except KeyboardInterrupt:
            print("Interrupted while initializing Video Intelligence client")
            raise
    return _CLIENT

def _try_cancel(operation):
    """Best-effort cancel for long-running operations on interrupt."""
    try:
        operation.cancel()
    except Exception:
        pass

def get_storage_client():
    """Lazily initialize the Cloud Storage client (only if needed)."""
    global _STORAGE_CLIENT
    if _STORAGE_CLIENT is None:
        if gcs_storage is None:
            raise RuntimeError(
                "google-cloud-storage is not installed; cannot upload to GCS. "
                "Install dependency and set GCS_BUCKET to enable uploads."
            )
        try:
            _STORAGE_CLIENT = gcs_storage.Client()
        except KeyboardInterrupt:
            print("Interrupted while initializing Cloud Storage client")
            raise
    return _STORAGE_CLIENT

def upload_to_gcs(local_path):
    """Upload a local file to GCS and return gs:// URI.

    Requires env var GCS_BUCKET; optional GCS_PREFIX for path prefix.
    """
    bucket_name = os.environ.get("GCS_BUCKET")
    if not bucket_name:
        raise RuntimeError("GCS_BUCKET env var is required to upload videos to GCS")
    prefix = os.environ.get("GCS_PREFIX", "video-intel")
    # Normalize path components
    prefix_clean = prefix.strip("/")
    blob_name = f"{prefix_clean}/{os.path.basename(local_path)}" if prefix_clean else os.path.basename(local_path)
    client = get_storage_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    print(f"Uploading to gs://{bucket_name}/{blob_name} ...")
    try:
        blob.upload_from_filename(local_path)
    except KeyboardInterrupt:
        # Best effort cleanup of partially uploaded object
        try:
            blob.delete()
        except Exception:
            pass
        print("Interrupted during upload; aborted and cleaned up if possible")
        raise
    return f"gs://{bucket_name}/{blob_name}"

FEATURES = [
    videointelligence.Feature.LABEL_DETECTION,
    videointelligence.Feature.SHOT_CHANGE_DETECTION,
    videointelligence.Feature.EXPLICIT_CONTENT_DETECTION,
    videointelligence.Feature.OBJECT_TRACKING,
    videointelligence.Feature.PERSON_DETECTION,
    videointelligence.Feature.FACE_DETECTION,
    videointelligence.Feature.TEXT_DETECTION,
    videointelligence.Feature.LOGO_RECOGNITION,
    videointelligence.Feature.SPEECH_TRANSCRIPTION,
]

MAX_UPLOAD_BYTES = 524288000  # 500 MB API limit

def time_offset_to_sec(time_offset):
    # Handle protobuf Duration (seconds+nanos) and potential datetime.timedelta
    if hasattr(time_offset, "seconds") and hasattr(time_offset, "nanos"):
        return float(time_offset.seconds) + float(time_offset.nanos) / 1e9
    if hasattr(time_offset, "total_seconds"):
        return float(time_offset.total_seconds())
    if hasattr(time_offset, "seconds") and hasattr(time_offset, "microseconds"):
        return float(time_offset.seconds) + float(time_offset.microseconds) / 1e6
    return 0.0

def _get_operation_timeout():
    """Return timeout (seconds) for LRO result(), or None for no timeout.

    Controlled via env var VI_TIMEOUT_SECONDS. Values <=0 or invalid -> None.
    """
    raw = os.environ.get("VI_TIMEOUT_SECONDS")
    if not raw:
        return None
    try:
        val = float(raw)
        if val <= 0:
            return None
        return val
    except Exception:
        return None

def analyze_video(file_path):
    # Decide whether to upload to GCS or send inline bytes
    force_gcs = os.environ.get("FORCE_GCS", "false").lower() in ("1", "true", "yes")
    size_bytes = None
    try:
        size_bytes = os.path.getsize(file_path)
    except OSError:
        pass

    use_gcs = force_gcs or (size_bytes is not None and size_bytes > MAX_UPLOAD_BYTES)
    input_content = None
    input_uri = None
    if use_gcs:
        input_uri = upload_to_gcs(file_path)
    else:
        with open(file_path, "rb") as f:
            input_content = f.read()

    try:
        client = get_client()
        # Enrich results using detection configs; be compatible across library versions
        vc_kwargs = {}

        # Label detection config (prefer SHOT_AND_FRAME mode if enum is available)
        try:
            ld_kwargs = {"stationary_camera": False, "model": "builtin/latest"}
            try:
                # Enum may be generated at module level in some versions
                ld_kwargs["label_detection_mode"] = videointelligence.LabelDetectionMode.SHOT_AND_FRAME_MODE
            except Exception:
                # Fallback: skip setting label_detection_mode if enum path not present
                pass
            vc_kwargs["label_detection_config"] = videointelligence.LabelDetectionConfig(**ld_kwargs)
        except Exception:
            pass

        # Person detection config (include detailed attributes where supported)
        try:
            vc_kwargs["person_detection_config"] = videointelligence.PersonDetectionConfig(
                include_bounding_boxes=True,
                include_pose_landmarks=True,
                include_attributes=True,
            )
        except Exception:
            pass

        # Text detection config (language hints; omit model if unsupported)
        try:
            vc_kwargs["text_detection_config"] = videointelligence.TextDetectionConfig(
                language_hints=["ru", "en"],
            )
        except Exception:
            pass

        # Speech transcription config for Russian (following official example)
        try:
            vc_kwargs["speech_transcription_config"] = videointelligence.SpeechTranscriptionConfig(
                language_code="ru-RU",
                enable_automatic_punctuation=True
            )
        except Exception:
            pass

        request_payload = {"features": FEATURES}
        if input_uri:
            request_payload["input_uri"] = input_uri
        else:
            request_payload["input_content"] = input_content
        if vc_kwargs:
            request_payload["video_context"] = videointelligence.VideoContext(**vc_kwargs)

        # First request: All features EXCEPT speech transcription
        features_no_speech = [f for f in FEATURES if f != videointelligence.Feature.SPEECH_TRANSCRIPTION]
        request_main = {"features": features_no_speech}
        if input_uri:
            request_main["input_uri"] = input_uri
        else:
            request_main["input_content"] = input_content
        if vc_kwargs_no_speech := {k: v for k, v in vc_kwargs.items() if k != "speech_transcription_config"}:
            request_main["video_context"] = videointelligence.VideoContext(**vc_kwargs_no_speech)

        print(f"Processing {file_path} (main features: labels, objects, text, etc.)...")
        operation_main = client.annotate_video(request=request_main)
        try:
            result_main = operation_main.result(timeout=_get_operation_timeout())
        except KeyboardInterrupt:
            _try_cancel(operation_main)
            print("Interrupted during main analysis; cancelling request...")
            raise

        # Second request: Speech transcription only
        speech_config = videointelligence.SpeechTranscriptionConfig(
            language_code="ru-RU",
            enable_automatic_punctuation=True
        )
        request_speech = {
            "features": [videointelligence.Feature.SPEECH_TRANSCRIPTION],
            "video_context": videointelligence.VideoContext(speech_transcription_config=speech_config)
        }
        if input_uri:
            request_speech["input_uri"] = input_uri
        else:
            request_speech["input_content"] = input_content

        print(f"Processing {file_path} (speech transcription)...")
        operation_speech = client.annotate_video(request=request_speech)
        try:
            result_speech = operation_speech.result(timeout=_get_operation_timeout())
        except KeyboardInterrupt:
            _try_cancel(operation_speech)
            print("Interrupted during speech transcription; cancelling request...")
            raise

        # Use main result as base (has labels, objects, text, etc.)
        result = result_main
        
        # Add speech transcriptions from the speech-only request
        if (result_speech.annotation_results and 
            len(result_speech.annotation_results) > 0 and
            hasattr(result_speech.annotation_results[0], 'speech_transcriptions')):
            
            # Ensure the main result has speech_transcriptions attribute
            if not hasattr(result.annotation_results[0], 'speech_transcriptions'):
                # Create empty speech_transcriptions if it doesn't exist
                result.annotation_results[0].speech_transcriptions = []
            
            # Copy speech transcriptions from speech result to main result
            result.annotation_results[0].speech_transcriptions = result_speech.annotation_results[0].speech_transcriptions
            print(f"Added {len(result_speech.annotation_results[0].speech_transcriptions)} speech transcription segments")
    except Exception as e:
        print(f"API error processing {file_path}: {e}")
        raise

    annotations = result.annotation_results[0]

    output = {
        "video_file": os.path.basename(file_path),
        "labels": [],
        "objects": [],
        "persons": [],
        "explicit_content": [],
        "text": [],
        "logos": [],
        "speech": [],
        "shots": [],
    }

    # Segment-level labels
    try:
        segment_labels = getattr(annotations, "segment_label_annotations", [])
        shot_labels = getattr(annotations, "shot_label_annotations", [])
        print(f"Found {len(segment_labels)} segment labels and {len(shot_labels)} shot labels")
        
        for label in segment_labels:
            for seg in label.segments:
                start = time_offset_to_sec(seg.segment.start_time_offset)
                end = time_offset_to_sec(seg.segment.end_time_offset)
                output["labels"].append({
                    "description": label.entity.description,
                    "category": [cat.description for cat in label.category_entities],
                    "confidence": seg.confidence,
                    "start_time": start,
                    "end_time": end
                })
                
        # Also add shot-level labels
        for label in shot_labels:
            for seg in label.segments:
                start = time_offset_to_sec(seg.segment.start_time_offset)
                end = time_offset_to_sec(seg.segment.end_time_offset)
                output["labels"].append({
                    "description": label.entity.description,
                    "category": [cat.description for cat in label.category_entities],
                    "confidence": seg.confidence,
                    "start_time": start,
                    "end_time": end
                })
    except Exception as e:
        print(f"Error processing labels: {e}")
        import traceback
        traceback.print_exc()

    # Object tracking
    try:
        for obj in annotations.object_annotations:
            track = {
                "entity": obj.entity.description,
                "confidence": obj.confidence,
                "frames": []
            }
            for frame in obj.frames:
                frame_data = {
                    "time": time_offset_to_sec(frame.time_offset),
                    "bbox": {
                        "left": frame.normalized_bounding_box.left,
                        "top": frame.normalized_bounding_box.top,
                        "right": frame.normalized_bounding_box.right,
                        "bottom": frame.normalized_bounding_box.bottom,
                    }
                }
                track["frames"].append(frame_data)
            output["objects"].append(track)
    except Exception:
        pass

    # Person detection
    try:
        for person in annotations.person_detection_annotations:
            person_data = {"tracks": []}
            for track in person.tracks:
                track_data = {
                    "segment": {
                        "start_time": time_offset_to_sec(track.segment.start_time_offset),
                        "end_time": time_offset_to_sec(track.segment.end_time_offset),
                    },
                    "landmarks": []
                }
                for timestamped_obj in track.timestamped_objects:
                    lm = []
                    for landmark in timestamped_obj.landmarks:
                        # Compatible extraction of landmark type across versions
                        landmark_type_name = None
                        try:
                            enum_val = getattr(landmark, "type_", None) or getattr(landmark, "type", None)
                            landmark_type_name = getattr(enum_val, "name", str(enum_val)) if enum_val is not None else None
                        except Exception:
                            landmark_type_name = None
                        item = {
                            "position": {
                                "x": landmark.point.x,
                                "y": landmark.point.y,
                            },
                            "confidence": getattr(landmark, "confidence", 0.0),
                        }
                        if landmark_type_name is not None:
                            item["type"] = landmark_type_name
                        lm.append(item)
                    track_data["landmarks"].append({
                        "time": time_offset_to_sec(timestamped_obj.time_offset),
                        "landmarks": lm
                    })
                person_data["tracks"].append(track_data)
            output["persons"].append(person_data)
    except Exception:
        pass

    # Explicit content
    try:
        for frame in annotations.explicit_annotation.frames:
            output["explicit_content"].append({
                "time": time_offset_to_sec(frame.time_offset),
                "pornography_likelihood": frame.pornography_likelihood.name
            })
    except Exception:
        pass

    # Shot change annotations
    try:
        for shot in annotations.shot_annotations:
            start = time_offset_to_sec(shot.start_time_offset)
            end = time_offset_to_sec(shot.end_time_offset)
            output["shots"].append({"start": start, "end": end})
    except Exception:
        pass

    # Text (OCR) annotations
    try:
        for text_ann in annotations.text_annotations:
            item = {
                "text": getattr(text_ann, "text", ""),
                "segments": []
            }
            for seg in text_ann.segments:
                start = time_offset_to_sec(seg.segment.start_time_offset)
                end = time_offset_to_sec(seg.segment.end_time_offset)
                item["segments"].append({
                    "start": start,
                    "end": end,
                    "confidence": getattr(seg, "confidence", 0.0),
                })
            output["text"].append(item)
    except Exception:
        pass

    # Logo recognition annotations
    try:
        for logo in annotations.logo_recognition_annotations:
            entry = {
                "entity": getattr(logo.entity, "description", ""),
                "tracks": []
            }
            for tr in logo.tracks:
                entry["tracks"].append({
                    "segment": {
                        "start": time_offset_to_sec(tr.segment.start_time_offset),
                        "end": time_offset_to_sec(tr.segment.end_time_offset),
                    },
                    "confidence": getattr(tr, "confidence", 0.0),
                })
            output["logos"].append(entry)
    except Exception:
        pass

    # Speech transcription annotations
    try:
        speech_transcriptions = getattr(annotations, "speech_transcriptions", [])
        print(f"Found {len(speech_transcriptions)} speech transcription segments")
        
        for st in speech_transcriptions:
            alternatives = getattr(st, "alternatives", [])
            print(f"  Segment has {len(alternatives)} alternatives")
            
            for alt in alternatives:
                speech_item = {
                    "transcript": getattr(alt, "transcript", ""),
                    "confidence": getattr(alt, "confidence", 0.0),
                    "words": []
                }
                words = getattr(alt, "words", [])
                print(f"    Alternative has {len(words)} words: '{speech_item['transcript'][:50]}...'")
                
                for w in words:
                    speech_item["words"].append({
                        "word": getattr(w, "word", ""),
                        "start": time_offset_to_sec(getattr(w, "start_time", 0)),
                        "end": time_offset_to_sec(getattr(w, "end_time", 0)),
                    })
                output["speech"].append(speech_item)
    except Exception as e:
        print(f"Error processing speech transcriptions: {e}")
        import traceback
        traceback.print_exc()

    # Save to JSON
    json_file = file_path + ".json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Saved annotations to {json_file}")

def find_clips_for_video(video_base_name):
    """Find all clips for a given video base name (e.g., 'jplmUJNfzJA')"""
    clips = []
    for fname in os.listdir(VIDEO_DIR):
        if fname.lower().endswith((".mp4", ".mov", ".avi", ".mkv", ".webm")):
            # Check if this file matches the pattern: {base_name}_clip{number}.{ext}
            if fname.startswith(f"{video_base_name}_clip"):
                clips.append(os.path.join(VIDEO_DIR, fname))
    
    # Sort clips by clip number
    clips.sort(key=lambda x: x)
    return clips

def process_video_argument(arg):
    """Process a single argument - could be a file path or video base name"""
    if os.path.exists(arg):
        # It's a direct file path
        return [arg]
    
    # Check if it's a video base name (like 'videos/jplmUJNfzJA')
    if arg.startswith('videos/'):
        video_base_name = arg[7:]  # Remove 'videos/' prefix
    else:
        video_base_name = arg
    
    # Find all clips for this video base name
    clips = find_clips_for_video(video_base_name)
    if clips:
        print(f"Found {len(clips)} clips for video '{video_base_name}':")
        for clip in clips:
            print(f"  - {os.path.basename(clip)}")
        return clips
    
    # If no clips found, maybe it's a malformed path
    print(f"No clips found for video base name '{video_base_name}' and path doesn't exist: {arg}")
    return []

if __name__ == "__main__":
    import sys
    try:
        if len(sys.argv) > 1:
            # Process specific file(s) or video base name(s) provided as arguments
            all_files_to_process = []
            
            for arg in sys.argv[1:]:
                files = process_video_argument(arg)
                all_files_to_process.extend(files)
            
            # Process all found files
            for file_path in all_files_to_process:
                try:
                    analyze_video(file_path)
                except Exception as e:
                    print(f"Error with {file_path}: {e}")
        else:
            # Process all videos in the directory
            for fname in os.listdir(VIDEO_DIR):
                if fname.lower().endswith((".mp4", ".mov", ".avi", ".mkv", ".webm")):
                    file_path = os.path.join(VIDEO_DIR, fname)
                    try:
                        analyze_video(file_path)
                    except Exception as e:
                        print(f"Error with {fname}: {e}")
    except KeyboardInterrupt:
        print("Interrupted by user. Exiting.")
        sys.exit(130)


