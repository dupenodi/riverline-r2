import { Button } from "./Button";
import { Icon } from "./Icon";
import styles from "./atoms.module.css";

type DockProps = {
  muted?: boolean;
  onMute?: () => void;
  onEnd?: () => void;
  ending?: boolean;
};

export function Dock({
  muted = false,
  onMute,
  onEnd,
  ending = false,
}: DockProps) {
  return (
    <div className={styles.dock}>
      <Button
        variant={muted ? "chip" : "ghost"}
        onClick={onMute}
        type="button"
        disabled={ending}
        aria-pressed={muted}
        aria-keyshortcuts="m"
        title="Mute (M)"
      >
        <Icon name={muted ? "microphone-slash" : "microphone"} size={12} />
        {muted ? "Unmute" : "Mute"}
      </Button>
      <Button
        variant="danger"
        onClick={onEnd}
        type="button"
        disabled={ending}
        aria-keyshortcuts="e"
        title="End call (E)"
      >
        <Icon name="phone-slash" size={12} />
        {ending ? "Ending…" : "End"}
      </Button>
    </div>
  );
}
