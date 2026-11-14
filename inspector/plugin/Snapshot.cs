using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UIElements;

namespace Crimson.Inspector
{
    // 0.1.1: one flat snapshot per frame. The first walk-based tool in a frame builds it (budget-capped,
    // resumable inside the frame); find / screen / dump_tree then serve from the captured nodes, so the
    // IL2CPP tree is walked at most once per frame and find stays inside the main-thread budget
    // (0.1.0 find walked and matched per element: 52 ms on the match screen, over the 40 ms budget).
    internal sealed class Snap
    {
        internal sealed class Node
        {
            public VisualElement El;
            public string Path;
            public string Type;
            public string Name;
            public List<string> Classes;
            public string Label;
            public string Text;
            public bool Visible;
            public int Depth;
            public float X, Y, W, H;
        }

        // One tree position on the DFS stack; Next is the next child index to descend into.
        private struct Open
        {
            public VisualElement El;
            public string Path;
            public int Depth, Next;
        }

        public readonly List<Node> Nodes = new List<Node>(4096);
        public readonly int Frame;
        public bool Complete;

        private readonly List<Open> _stack = new List<Open>(256);
        private static Snap _current;

        private Snap(int frame) { Frame = frame; }

        // The snapshot for the current frame: rebuilt when the frame advances, continued when a later
        // request in the same frame finds it partial (the walk resumes where it stopped).
        public static Snap Get(Budget budget)
        {
            int frame = Time.frameCount;
            if (_current == null || _current.Frame != frame)
            {
                _current = new Snap(frame);
                var roots = Ui.Roots();
                for (int i = roots.Count - 1; i >= 0; i--)
                    _current._stack.Add(new Open { El = roots[i].Element, Path = "P" + i, Depth = 0, Next = 0 });
            }
            _current.Advance(budget);
            return _current;
        }

        public bool Partial => !Complete;

        // Depth-first pre-order (same order as the 0.1.0 walk); nodes are captured once, on first visit.
        private void Advance(Budget budget)
        {
            if (Complete) return;
            while (_stack.Count > 0 && !budget.Spent)
            {
                int i = _stack.Count - 1;
                Open top = _stack[i];
                if (top.Next == 0)
                {
                    // Own resolved state only: visibility is inherited in USS and a child can re-enable
                    // visibility:visible under a hidden parent (the Card-frame wallpaper trick), so a
                    // hidden parent must NOT mark its children invisible.
                    Rect b = top.El.worldBound;
                    List<string> classes = Ui.Classes(top.El);
                    Nodes.Add(new Node
                    {
                        El = top.El,
                        Path = top.Path,
                        Type = Ui.TypeName(top.El),
                        Name = top.El.name ?? "",
                        Classes = classes,
                        Label = Ui.Label(top.El, classes),
                        Text = Ui.Text(top.El),
                        Visible = Ui.SelfVisible(top.El),
                        Depth = top.Depth,
                        X = b.x, Y = b.y, W = b.width, H = b.height,
                    });
                }
                int n = top.El.hierarchy.childCount;
                if (top.Next < n)
                {
                    Open child = new Open { El = top.El.hierarchy.ElementAt(top.Next), Path = top.Path + "/" + top.Next,
                        Depth = top.Depth + 1, Next = 0 };
                    top.Next++;
                    _stack[i] = top;
                    _stack.Add(child);
                }
                else
                {
                    _stack.RemoveAt(i);
                }
            }
            Complete = _stack.Count == 0;
        }
    }
}
