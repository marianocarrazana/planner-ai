import { Children, cloneElement, isValidElement, type ReactElement, type ReactNode } from "react";

interface ClickableProps {
  onClick: () => void;
  children: ReactNode;
}

/**
 * OpenTUI text is selectable by default and swallows mouse button events
 * (https://github.com/sst/opentui/issues/112). Force selectable={false} and
 * attach onMouseDown on the text child so clicks reach the handler.
 */
export function Clickable({ onClick, children }: ClickableProps) {
  return (
    <box
      onMouseDown={() => {
        onClick();
      }}
    >
      {Children.map(children, (child) => {
        if (!isValidElement(child)) return child;
        return cloneElement(child as ReactElement<Record<string, unknown>>, {
          selectable: false,
          onMouseDown: () => {
            onClick();
          },
        });
      })}
    </box>
  );
}
